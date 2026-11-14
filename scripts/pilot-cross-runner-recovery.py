#!/usr/bin/env python3
"""Synthetic NEXUS cold backup and recovery on separate ephemeral CI jobs.

Never connect to provider production, accept a user volume, upload real data, or
interpret test success as a production restore / release authorization.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SNAPSHOT = HERE / "data-snapshot.py"
IMAGE = "nexus-cross-runner:ci"
DATASET = "cross-runner-synthetic"
REQUEST = "cross-runner-synthetic-accepted"
ARCHIVE_NAME = "synthetic-volume-snapshot.json"
RECEIPT_NAME = "synthetic-recovery-receipt.json"
RECEIPT_SCHEMA = "nexus.synthetic-cross-runner-recovery.v1"
SHA = re.compile(r"[0-9a-f]{40}\Z")
SHADIGEST = re.compile(r"[0-9a-f]{64}\Z")
ALLOWED_KEYS = {
    "schema", "candidate_sha", "archive_sha256", "workspace_sha256",
    "snapshot_file_count", "origin", "authority", "contains_user_data",
    "production_backup", "production_restore", "seal"
}


def require(condition, reason):
    if not condition:
        raise AssertionError(reason)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate-receipt-property")
        result[key] = value
    return result


def clean_environment():
    require(os.environ.get("GITHUB_ACTIONS") == "true", "github-ci-only")
    require(os.environ.get("NEXUS_CROSS_RUNNER_TEST") == "true", "not-disposable")
    require(re.fullmatch(r"[0-9]{1,18}", os.environ.get("GITHUB_RUN_ID", "")) is not None,
            "invalid-run-id")
    require(SHA.fullmatch(os.environ.get("GITHUB_SHA", "")) is not None, "invalid-sha")
    require(not any(os.environ.get(x) for x in (
        "RAILWAY_TOKEN", "RAILWAY_API_TOKEN", "RENDER_API_KEY",
        "NEXUS_API_TOKEN", "GITHUB_TOKEN", "GH_TOKEN")), "operator-credential-present")
    # GitHub provides this temp directory separately to each newly hosted job.
    scratch = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    require(scratch.is_dir() and not scratch.is_relative_to(ROOT), "unsafe-scratch-dir")
    local_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    require(local_sha == os.environ["GITHUB_SHA"], "checkout-not-exact-candidate")
    return scratch, local_sha


def exec_checked(args, *, timeout=120, env=None):
    completed = subprocess.run([str(x) for x in args], env=env,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL,
                               stdin=subprocess.DEVNULL, check=False, timeout=timeout)
    require(completed.returncode == 0, "disposable-subprocess-failed")


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())


def http(port_number, method, route, *, token=None, data=None):
    require(re.fullmatch(r"/[A-Za-z0-9/_-]+", route) is not None, "invalid-route")
    raw = None if data is None else canonical(data)
    headers = {"Accept": "application/json"}
    if raw is not None:
        headers["Content-Type"] = "application/json"
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(
        f"http://127.0.0.1:{port_number}{route}", data=raw, headers=headers, method=method)
    try:
        response = OPENER.open(request, timeout=4)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        body = response.read(1024 * 1024 + 1)
        require(len(body) <= 1024 * 1024, "unbounded-response")
        return response.status, json.loads(body, object_pairs_hook=unique)


def await_readiness(port_number, expected):
    end = time.monotonic() + 55
    while time.monotonic() < end:
        try:
            status, payload = http(port_number, "GET", "/readyz")
            if (status, payload) == (expected, {"status": "ready" if expected == 200
                                                     else "quarantined"}):
                return
        except (OSError, ValueError, AssertionError, TimeoutError):
            pass
        time.sleep(0.3)
    raise AssertionError("gateway-did-not-become-ready")


def start_container(name, store, port_number, token):
    # Pass only an ephemeral test bearer through process environment, not CLI.
    env = dict(os.environ)
    env["NEXUS_API_TOKEN"] = token
    exec_checked(["docker", "run", "-d", "--name", name,
                  "--publish", f"127.0.0.1:{port_number}:3000",
                  "--env", "NEXUS_API_TOKEN",
                  "--env", "NEXUS_DATA_DIR=/data",
                  "--mount", f"type=bind,source={store},target=/data",
                  IMAGE], timeout=45, env=env)


def stop_container(name):
    exec_checked(["docker", "stop", "-t", "8", name], timeout=30)
    exec_checked(["docker", "rm", name], timeout=30)


def cleanup_container(name):
    subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                   check=False, timeout=15)


def source(scratch, sha):
    os.umask(0o077)
    output = scratch / "nexus-synthetic-transfer"
    require(not output.exists(), "output-already-exists")
    output.mkdir(mode=0o700)
    store = Path(tempfile.mkdtemp(prefix="nexus-cross-src-", dir=scratch))
    p = port()
    token = secrets.token_urlsafe(48)
    name = "nexus-cross-source-" + os.environ["GITHUB_RUN_ID"]
    try:
        start_container(name, store, p, token)
        await_readiness(p, 200)
        code, created = http(p, "POST", "/v1/workspaces", token=token, data={
            "workspace_id": DATASET, "question": "Synthetic independent recovery drill",
            "provenance_id": "fixture:cross-runner"})
        require(code == 201 and created.get("workspace", {}).get("id") == DATASET,
                "workspace-create-failed")
        code, created = http(p, "POST", "/v1/workspaces/" + DATASET + "/claims",
                             token=token, data={
            "text": "Synthetic evidence cannot become human judgment",
            "origin": {"kind": "external_evidence", "source": "fixture:cross-runner"},
            "uncertainty": "high", "provenance_id": "fixture:source"})
        require(code == 200 and created["workspace"]["judgment"] is None,
                "claim-created-judgment")
        code, accepted = http(p, "POST", "/v1/requests", token=token, data={
            "request_id": REQUEST, "authority": "user", "action": "present",
            "value": "test-only", "payload": "opaque"})
        require(code == 202 and accepted["status"] == "pending", "request-not-pending")
        code, before = http(p, "GET", "/v1/workspaces/" + DATASET, token=token)
        require(code == 200 and len(before["events"]) >= 2, "incomplete-workspace")
        before_digest = digest(canonical(before))
        code, request_state = http(p, "GET", "/v1/requests/" + REQUEST, token=token)
        require((code, request_state.get("status")) == (200, "pending"),
                "source-ledger-missing")
        stop_container(name)  # All writers stopped BEFORE archive acquisition.
        archive = output / ARCHIVE_NAME
        exec_checked([sys.executable, SNAPSHOT, "backup", store, archive, "--offline"])
        inspection = subprocess.check_output(
            [sys.executable, str(SNAPSHOT), "inspect", str(archive)], text=True)
        metadata = json.loads(inspection, object_pairs_hook=unique)
        require(metadata["status"] == "STRUCTURALLY_VALID" and
                metadata["workspace_count"] == 1 and
                metadata["requests"]["pending"] >= 1 and
                metadata["captured_quarantine"] is False, "incomplete-archive")
        receipt = {
            "schema": RECEIPT_SCHEMA, "candidate_sha": sha,
            "archive_sha256": digest(archive.read_bytes()),
            "workspace_sha256": before_digest,
            "snapshot_file_count": metadata["file_count"],
            "origin": "synthetic-disposable-github-job",
            "authority": "none", "contains_user_data": False,
            "production_backup": False, "production_restore": False,
            "seal": False,
        }
        (output / RECEIPT_NAME).write_bytes(canonical(receipt) + b"\n")
        print("CROSS RUNNER SOURCE: SYNTHETIC BACKUP PASS", flush=True)
    finally:
        cleanup_container(name)
        shutil.rmtree(store, ignore_errors=True)
    return output


def receipt_check(receipt_path, archive_path, sha):
    require(not receipt_path.is_symlink() and not archive_path.is_symlink(),
            "symlink-artifact")
    require(0 < receipt_path.stat().st_size <= 16384, "receipt-bounds")
    require(0 < archive_path.stat().st_size <= 64 * 1024 * 1024, "archive-bounds")
    value = json.loads(receipt_path.read_bytes(), object_pairs_hook=unique)
    require(type(value) is dict and set(value) == ALLOWED_KEYS, "wrong-receipt-shape")
    require(value["schema"] == RECEIPT_SCHEMA and value["candidate_sha"] == sha,
            "wrong-candidate")
    require(value["origin"] == "synthetic-disposable-github-job" and
            value["authority"] == "none", "wrong-origin")
    require(all(value[k] is False for k in (
        "contains_user_data", "production_backup", "production_restore", "seal")),
        "claim-expansion")
    require(type(value["snapshot_file_count"]) is int and
            2 <= value["snapshot_file_count"] <= 20000, "file-count-invalid")
    require(type(value["archive_sha256"]) is str and
            SHADIGEST.fullmatch(value["archive_sha256"]) is not None and
            digest(archive_path.read_bytes()) == value["archive_sha256"], "archive-drift")
    require(type(value["workspace_sha256"]) is str and
            SHADIGEST.fullmatch(value["workspace_sha256"]) is not None, "workspace-digest-invalid")
    return value


def target(scratch, sha, input_dir):
    os.umask(0o077)
    require(input_dir.resolve().is_relative_to(scratch), "external-archive-disallowed")
    archive = input_dir / ARCHIVE_NAME
    receipt = input_dir / RECEIPT_NAME
    metadata = receipt_check(receipt, archive, sha)
    store = scratch / "nexus-disposable-recovery"
    require(not store.exists(), "restore-destination-already-exists")
    # A corrupted archive MUST be rejected and cannot create a target.
    damaged = scratch / "nexus-synthetic-corrupt.json"
    raw = archive.read_bytes()
    damaged.write_bytes(b"!" + raw[1:])
    proc = subprocess.run(
        [sys.executable, str(SNAPSHOT), "restore", str(damaged), str(store), "--offline"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL, timeout=12, check=False)
    require(proc.returncode != 0 and not store.exists(), "corruption-bypass")
    damaged.unlink()
    exec_checked(["sudo", sys.executable, SNAPSHOT, "restore", archive,
                  store, "--offline", "--owner", "10001:10001"], timeout=35)
    marker = store / ".nexus-recovery-required"
    # Restored files are deliberately owned by the gateway UID and mode 0600.
    # Inspect using a constrained read-only sudo witness; the runner account
    # must not gain permission to read private restored files.
    exec_checked(["sudo", sys.executable, "-c",
                  "from pathlib import Path; import sys; "
                  "assert Path(sys.argv[1]).read_bytes() == "
                  "b'snapshot-restored; replay-risk-not-acknowledged\\n'",
                  marker], timeout=10)
    p = port()
    token = secrets.token_urlsafe(48)
    name = "nexus-cross-restore-" + os.environ["GITHUB_RUN_ID"]
    try:
        start_container(name, store, p, token)
        await_readiness(p, 503)
        code, restored = http(p, "GET", "/v1/workspaces/" + DATASET, token=token)
        require(code == 200 and digest(canonical(restored)) ==
                metadata["workspace_sha256"], "restored-workspace-drift")
        code, state = http(p, "GET", "/v1/requests/" + REQUEST, token=token)
        require((code, state.get("status")) == (200, "pending"),
                "pending-ledger-not-recovered")
        code, _ = http(p, "GET", "/v1/workspaces/" + DATASET)
        require(code == 401, "unauthenticated-data-exposed")
        code, _ = http(p, "POST", "/v1/requests", token=token, data={
            "request_id": REQUEST + "-quarantine", "authority": "user",
            "action": "present", "value": "test", "payload": "opaque"})
        require(code == 503, "quarantine-writes-allowed")
        stop_container(name)
        exec_checked(["sudo", sys.executable, SNAPSHOT, "resume", store, "--offline",
                      "--acknowledge-replay-risk"], timeout=35)
        start_container(name, store, p, token)
        await_readiness(p, 200)
        code, _ = http(p, "POST", "/v1/requests", token=token, data={
            "request_id": REQUEST, "authority": "user",
            "action": "present", "value": "test", "payload": "opaque"})
        require(code == 409, "replayed-request-was-accepted")
        code, _ = http(p, "POST", "/v1/requests", token=token, data={
            "request_id": REQUEST + "-after", "authority": "user",
            "action": "present", "value": "test", "payload": "opaque"})
        require(code == 202, "post-resume-new-request-rejected")
        print(json.dumps({
            "schema": RECEIPT_SCHEMA,
            "status": "PASS_SYNTHETIC_SEPARATE_RUNNER_RECOVERY",
            "candidate_sha": sha,
            "workspace_integrity": True,
            "request_ledger": True,
            "unauthenticated_access_rejected": True,
            "quarantined_write_refused": True,
            "replay_rejected": True,
            "new_write_after_synthetic_resume": True,
            "provider_data_read": False,
            "production_backup": False,
            "production_restore": False,
            "release_authorized": False,
            "seal": False, "authority": "none"
        }, sort_keys=True))
    finally:
        cleanup_container(name)
        # The target is test-only ephemeral runner storage; no live volume.
        subprocess.run(["sudo", "rm", "-rf", "--", str(store)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       stdin=subprocess.DEVNULL, timeout=15, check=False)


def self_test():
    assert digest(b"test") == hashlib.sha256(b"test").hexdigest()
    try:
        unique([("a", 1), ("a", 2)])
        raise AssertionError("duplicate-field-accepted")
    except AssertionError as error:
        require(str(error) == "duplicate-receipt-property", "wrong-duplicate-error")
    require(SHA.fullmatch("a" * 40) is not None, "invalid-commit-pattern")
    require(not SHA.fullmatch("a" * 41), "overlong-commit-accepted")
    try:
        http(9, "GET", "/v1/data?token=unsafe")
        raise AssertionError("unsafe-route-accepted")
    except AssertionError as error:
        require(str(error) == "invalid-route", "wrong-route-error")
    print("CROSS RUNNER SYNTHETIC SELF-TEST: PASS")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["produce", "recover", "self-test"])
    parser.add_argument("--artifact-dir", type=Path)
    args = parser.parse_args()
    if args.operation == "self-test":
        self_test()
        return
    scratch, sha = clean_environment()
    if args.operation == "produce":
        require(args.artifact_dir is None, "unexpected-input")
        source(scratch, sha)
    else:
        require(args.artifact_dir is not None, "artifact-dir-required")
        target(scratch, sha, args.artifact_dir)


if __name__ == "__main__":
    main()
