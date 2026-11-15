#!/usr/bin/env python3
"""Exercise actual historical NEXUS gateway executables with synthetic data.

Only loopback 127.0.0.1, fresh private temporary roots, disposable bearer
tokens, no Railway/Render access. SIGKILL tests process-exit recovery, *not*
hardware power-loss durability. Expected legacy weaknesses are recorded as
findings and never interpreted as permission to downgrade or deploy.
"""
import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time

ROLES = ("recovery", "source", "target")
FULL_SHA = {
    "recovery": "588dc7672146031425b16b34956876d644244ace",
    "source": "9abbc067aad3ebbb0956432cf6682d2ea70e2824",
    "target": "f4d027bb5f7e715b298f7cf7184fa621a2fb071d",
}
REQUEST = "synthetic-request-001"
UNKNOWN = "synthetic-unknown"
UNCERTAIN = "synthetic-interrupted-marker"
WORKSPACE = "synthetic-workspace-001"
SYNTHETIC_BODY = {
    "request_id": REQUEST,
    "authority": "user",
    "action": "reflect",
    "subject": "disposable",
    "payload": "synthetic",
}


class GatewayTestError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise GatewayTestError(message)


def port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def http_call(p, token, method, route, data=None, authenticate=True):
    body = None if data is None else json.dumps(
        data, separators=(",", ":")).encode()
    conn = http.client.HTTPConnection("127.0.0.1", p, timeout=2.0)
    try:
        headers = {"Accept": "application/json"}
        if authenticate:
            headers["Authorization"] = "Bearer " + token
        if body is not None:
            headers["Content-Type"] = "application/json"
        conn.request(method, route, body=body, headers=headers)
        response = conn.getresponse()
        blob = response.read(1024 * 1024 + 1)
        require(len(blob) <= 1024 * 1024, "historical response exceeded size cap")
        try:
            value = json.loads(blob)
        except (ValueError, UnicodeError):
            value = {}
        return response.status, value
    finally:
        conn.close()


def start(binary, folder, role, token):
    p = port()
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(folder),
        "NEXUS_API_TOKEN": token,
        "NEXUS_DATA_DIR": str(folder),
        "NEXUS_BIND_ADDR": "127.0.0.1:" + str(p),
    }
    child = subprocess.Popen(
        [str(binary)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, cwd=str(folder), env=env,
        start_new_session=True, close_fds=True,
    )
    until = time.monotonic() + 12.0
    while time.monotonic() < until:
        if child.poll() is not None:
            raise GatewayTestError(role + ": historical service exited before accepting loopback")
        try:
            status, _ = http_call(p, token, "GET", "/v1/requests/" + UNKNOWN)
            if status == 404:
                return child, p
            raise GatewayTestError(role + ": unexpected startup response")
        except (OSError, TimeoutError, ConnectionError):
            time.sleep(0.07)
    stop(child)
    raise GatewayTestError(role + ": historical service never became ready")


def stop(child):
    if child is None or child.poll() is not None:
        return
    try:
        # All children belong to an isolated process group: no background
        # descendants should remain between individual version runs.
        os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        child.wait(timeout=4)
    except subprocess.TimeoutExpired:
        raise GatewayTestError("historical process group did not stop")


def check_file(path, data):
    meta = path.lstat()
    require(stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1,
            "request marker identity is not private regular file")
    require(path.read_bytes() == data, "persisted synthetic marker changed")


def exercise(role, binary, root):
    role_root = root / role
    role_root.mkdir(mode=0o700)
    token = secrets.token_urlsafe(32)
    main = None
    restarted = None
    cases = 0
    finding = "none"
    try:
        # Run actual program rather than imported Rust core/JSON parser.
        main, p = start(binary, role_root, role, token)
        status, _ = http_call(p, token, "POST", "/v1/requests", SYNTHETIC_BODY,
                              authenticate=False)
        require(status == 401, role + ": unauthenticated request must be refused")
        cases += 1
        status, data = http_call(
            p, token, "POST", "/v1/workspaces", {
                "workspace_id": WORKSPACE,
                "question": "Ephemeral question",
                "provenance_id": "human:rehearsal",
            })
        require(status == 201 and data.get("workspace", {}).get("id") == WORKSPACE,
                role + ": failed synthetic durable workspace create")
        cases += 1
        status, value = http_call(p, token, "POST", "/v1/requests", SYNTHETIC_BODY)
        require(status == 202 and value.get("request_id") == REQUEST,
                role + ": synthetic request was not accepted")
        cases += 1
        status, value = http_call(p, token, "GET", "/v1/requests/" + REQUEST)
        require(status == 200 and str(value.get("status", "")).lower() == "pending",
                role + ": synthetic request not queryable as pending before kill")
        cases += 1
        # Kill AFTER the HTTP 202, not during a real ambiguous transaction.
        # This is a deterministic process crash, not hardware fsync proof.
        stop(main)
        main = None
        if role != "recovery":
            check_file(role_root / "requests" / REQUEST.encode().hex(),
                       b"pending\n")
        else:
            require(not (role_root / "requests" / REQUEST.encode().hex()).exists(),
                    "legacy recovery unexpectedly wrote persistent request ledger")
        cases += 1

        restarted, p2 = start(binary, role_root, role, token)
        status, value = http_call(
            p2, token, "GET", "/v1/workspaces/" + WORKSPACE)
        require(status == 200 and value.get("workspace", {}).get("id") == WORKSPACE,
                role + ": workspace missing after SIGKILL/restart")
        cases += 1
        status, value = http_call(p2, token, "GET", "/v1/requests/" + REQUEST)
        if role == "recovery":
            require(status == 404 and value.get("error") == "request_not_found",
                    "unexpected legacy request status persistence")
            finding = "legacy_request_status_lost_after_restart"
        else:
            require(status == 200 and
                    str(value.get("status", "")).lower() == "pending",
                    "durable request status was lost on restart")
        cases += 1

        status, value = http_call(p2, token, "POST", "/v1/requests", SYNTHETIC_BODY)
        if role == "recovery":
            require(status == 202 and value.get("request_id") == REQUEST,
                    "legacy gateway replay acceptance unexpectedly changed")
            finding = "legacy_request_status_and_replay_protection_lost_after_restart"
        else:
            require(status == 409 and value.get("error") == "request_id_replayed",
                    "modern gateway allowed duplicate after restart")
        cases += 1
        stop(restarted)
        restarted = None

        # Durable partial reservation (1-byte marker) must reopen as
        # indeterminate, must never become 'pending' or be replayed.
        if role != "recovery":
            uncertain_file = role_root / "requests" / UNCERTAIN.encode().hex()
            flags = (os.O_WRONLY | os.O_CREAT | os.O_EXCL
                     | getattr(os, "O_NOFOLLOW", 0))
            fd = os.open(uncertain_file, flags, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(b"p")
                stream.flush()
                os.fsync(stream.fileno())
            cases += 1
            restarted, p3 = start(binary, role_root, role, token)
            status, value = http_call(
                p3, token, "GET", "/v1/requests/" + UNCERTAIN)
            require(status == 200 and
                    str(value.get("status", "")).lower() == "indeterminate",
                    "partial reservation was not conservatively quarantined")
            cases += 1
            request = dict(SYNTHETIC_BODY, request_id=UNCERTAIN)
            status, value = http_call(p3, token, "POST", "/v1/requests", request)
            require(status == 409 and value.get("error") == "request_id_replayed",
                    "partial reservation was incorrectly retried")
            cases += 1
            check_file(uncertain_file, b"p")
            cases += 1
            stop(restarted)
            restarted = None

            # Historical source + later target both have a startup-latched
            # recovery quarantine: no state-changing request may pass.
            quarantined = role_root / ".nexus-recovery-required"
            quarantined.write_bytes(b"snapshot-restored; replay-risk-not-acknowledged\n")
            os.chmod(quarantined, 0o600)
            restarted, pq = start(binary, role_root, role, token)
            status, value = http_call(
                pq, token, "POST", "/v1/requests",
                dict(SYNTHETIC_BODY, request_id="synthetic-quarantined"))
            require(status == 503 and
                    value.get("error") == "recovery_acknowledgment_required",
                    "recovery quarantine allowed a new request")
            cases += 1
            require(not (
                role_root / "requests" / "synthetic-quarantined".encode().hex()).exists(),
                "recovery quarantine wrote a forbidden request marker")
            cases += 1
            stop(restarted)
            restarted = None
        return {
            "role": role,
            "source_commit": FULL_SHA[role],
            "checks": cases,
            "finding": finding,
            "actual_historical_gateway_binary_executed": True,
            "process_sigkill_and_restart_exercised": True,
            "hardware_power_loss_proven": False,
            "service_data_schema_downgrade_proven": False,
            "production_release_authorized": False,
        }
    finally:
        stop(main)
        stop(restarted)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recovery-binary", required=True, type=Path)
    parser.add_argument("--source-binary", required=True, type=Path)
    parser.add_argument("--target-binary", required=True, type=Path)
    parser.add_argument("--runner-temp", required=True, type=Path)
    parser.add_argument("--synthetic-only", action="store_true", required=True)
    args = parser.parse_args()
    try:
        require(args.synthetic_only, "requires explicit synthetic-only boundary")
        require(args.runner_temp.is_absolute() and args.runner_temp.is_dir()
                and not args.runner_temp.is_symlink(),
                "must use isolated absolute temporary runner root")
        args.runner_temp = args.runner_temp.resolve(strict=True)
        for role in ROLES:
            path = getattr(args, role + "_binary")
            require(path.is_absolute() and path.is_file() and not path.is_symlink(),
                    role + " immutable binary missing")
        with tempfile.TemporaryDirectory(
                prefix="nexus-synthetic-gateway-", dir=args.runner_temp) as tmp:
            root = Path(tmp)
            os.chmod(root, 0o700)
            output = {
                role: exercise(role, getattr(args, role + "_binary"), root)
                for role in ROLES
            }
        require(output["recovery"]["finding"] ==
                "legacy_request_status_and_replay_protection_lost_after_restart",
                "historical loss of request idempotency must be explicitly recorded")
        require(all(output[role]["finding"] == "none"
                    for role in ("source", "target")),
                "newer gateways failed to preserve request idempotency")
        print(json.dumps({
            "status": "PASS_WITH_KNOWN_LEGACY_REPLAY_RISK",
            "checks": sum(v["checks"] for v in output.values()),
            "results": output,
            "real_historical_gateways_executed": True,
            "all_user_data_synthetic": True,
            "real_railway_or_render_touched": False,
            "hardware_power_loss_proven": False,
            "production_release_authorized": False,
            "release_gate": "BLOCKED",
        }, sort_keys=True))
        return 0
    except (GatewayTestError, OSError, ValueError, KeyError) as exc:
        print("NEXUS HISTORICAL GATEWAY REHEARSAL DENIED: " + str(exc),
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
