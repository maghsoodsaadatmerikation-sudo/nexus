#!/usr/bin/env python3
"""Exercise the actual Rust gateway on disposable local storage only.

No Render/Railway access, backup publication, release authority or real data.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ID = "1234567890abcdef1234567890abcdef"
WRONG = "abcdef1234567890abcdef1234567890"
TOKEN = "fixture-local-volume-test-only"
HERE = Path(__file__).resolve().parent


def require(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)


def port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def env_for(root: Path, port_number: int, volume_id=ID) -> dict:
    env = dict(os.environ)
    for key in ("RENDER_API_KEY", "RAILWAY_TOKEN", "RAILWAY_API_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        env.pop(key, None)
    env.update({
        "NEXUS_DATA_DIR": str(root),
        "NEXUS_BIND_ADDR": f"127.0.0.1:{port_number}",
        "NEXUS_API_TOKEN": TOKEN,
        "NEXUS_EXPECTED_VOLUME_ID": volume_id,
    })
    return env


def failed_startup(binary: Path, root: Path, volume_id=ID) -> None:
    proc = subprocess.Popen(
        [str(binary)], env=env_for(root, port(), volume_id),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )
    try:
        try:
            code = proc.wait(timeout=8)
        except subprocess.TimeoutExpired as exc:
            raise AssertionError("unknown volume incorrectly admitted traffic") from exc
        require(code != 0, "unknown volume started")
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=4)


def request(number: int, method: str, route: str, payload=None):
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if route.startswith("/v1/"):
        headers["Authorization"] = "Bearer " + TOKEN
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(
        f"http://127.0.0.1:{number}{route}", data=data, method=method,
        headers=headers,
    )
    try:
        resp = opener.open(req, timeout=3)
    except urllib.error.HTTPError as e:
        resp = e
    with resp:
        return resp.status, json.loads(resp.read(1024 * 1024))


def start(binary: Path, root: Path) -> tuple[subprocess.Popen, int]:
    number = port()
    proc = subprocess.Popen(
        [str(binary)], env=env_for(root, number),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )
    try:
        until = time.monotonic() + 12
        while time.monotonic() < until:
            require(proc.poll() is None, "valid enrolled volume rejected at startup")
            try:
                response = request(number, "GET", "/readyz")
                if response == (200, {"status": "ready"}):
                    return proc, number
            except (OSError, ValueError, urllib.error.URLError):
                pass
            time.sleep(.15)
        raise AssertionError("enrolled gateway readiness not achieved")
    except BaseException:
        proc.kill()
        proc.wait(timeout=4)
        raise


def stop(proc: subprocess.Popen):
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=4)


def exercise(binary: Path):
    with tempfile.TemporaryDirectory(prefix="nexus-volume-live-smoke-") as d:
        parent = Path(d)
        root = parent / "volume"
        failed_startup(binary, root)
        require(not root.exists(), "strict startup created missing replacement volume")
        root.mkdir()
        failed_startup(binary, root)
        require(not list(root.iterdir()), "strict startup wrote to empty foreign volume")
        failed_startup(binary, root, WRONG)
        require(not list(root.iterdir()), "wrong expected identity mutated root")

        command = [
            sys.executable, str(HERE / "enroll-new-volume.py"),
            str(root), "--volume-id", ID, "--offline",
            "--confirm", "I AM INITIALIZING A NEW EMPTY NEXUS DATA VOLUME",
        ]
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, timeout=7)

        gateway, p = start(binary, root)
        try:
            status, body = request(p, "POST", "/v1/workspaces", {
                "workspace_id": "retained",
                "question": "Synthetic persistence check",
                "provenance_id": "fixture:volume",
            })
            require(status == 201 and body["workspace"]["id"] == "retained",
                    "synthetic workspace create refused")
        finally:
            stop(gateway)

        gateway, p = start(binary, root)
        try:
            status, body = request(p, "GET", "/v1/workspaces/retained")
            require(status == 200 and body["workspace"]["id"] == "retained",
                    "restart lost synthetic workspace")
        finally:
            stop(gateway)

        moved = parent / "original"
        root.rename(moved)
        failed_startup(binary, root)
        require(not root.exists(), "lost volume silently recreated")
        root.mkdir()
        failed_startup(binary, root)
        require(not list(root.iterdir()), "new empty volume adopted")
        (root / ".nexus-volume-identity").write_bytes(
            b"nexus.volume-identity.v1\n" + WRONG.encode("ascii") + b"\n"
        )
        failed_startup(binary, root)
        require(len(list(root.iterdir())) == 1, "incorrect volume was mutated")
        for p in root.iterdir():
            p.unlink()
        root.rmdir()
        moved.rename(root)
        gateway, p = start(binary, root)
        try:
            status, body = request(p, "GET", "/v1/workspaces/retained")
            require(status == 200 and body["workspace"]["id"] == "retained",
                    "restored original volume was not reused")
        finally:
            stop(gateway)
        print("LIVE GATEWAY VOLUME IDENTITY: FAIL-CLOSED AND EXACT-RESTORE PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    args = parser.parse_args()
    try:
        require(args.binary.is_file(), "missing compiled Rust gateway binary")
        exercise(args.binary.resolve())
    except (OSError, AssertionError, subprocess.CalledProcessError, ValueError):
        print("LIVE GATEWAY VOLUME IDENTITY: FAIL", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
