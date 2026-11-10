#!/usr/bin/env python3
"""Pilot 05: cold synthetic source -> private copy -> new gateway restore.

Disposable GitHub Actions runner ONLY. No access to Railway, Render, public
endpoints, personal workspaces, or operator secrets. No network except loopback
Docker ports. Restored state remains quarantined until an explicit synthetic
replay-risk acknowledgment with all writers stopped.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "data-snapshot.py"
REPORT_NAME = "pilot-05-synthetic-recovery.json"
IMAGE = "nexus-pilot-05:ci"


def require(condition, name):
    if not condition:
        raise AssertionError(name)


def sha_json(obj):
    return hashlib.sha256(
        json.dumps(obj, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def run(*args, timeout=90):
    action = subprocess.run(
        [str(x) for x in args], stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=False, timeout=timeout)
    require(action.returncode == 0, "disposable-command-failed")


def safe_path(path):
    return (re.fullmatch(r"/[A-Za-z0-9/_-]*", path) is not None and
            not path.startswith("//") and "//" not in path)


def http(port, method, path, token=None, data=None):
    require(safe_path(path), "invalid-local-route")
    body = None if data is None else json.dumps(data, separators=(",", ":")).encode()
    headers = {"cache-control": "no-store"}
    if data is not None:
        headers["content-type"] = "application/json"
    if token is not None:
        headers["authorization"] = "Bearer " + token
    request = urllib.request.Request(
        "http://127.0.0.1:" + str(port) + path,
        data=body, method=method, headers=headers)
    try:
        response = urllib.request.urlopen(request, timeout=6)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read(1024 * 1024 + 1)
        require(len(raw) <= 1024 * 1024, "oversized-test-response")
        return response.status, json.loads(raw)


def ready(port, expected):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            status, data = http(port, "GET", "/readyz")
            if status == expected and data == {
                    "status": "quarantined" if expected == 503 else "ready"}:
                return
        except (OSError, ValueError, AssertionError):
            pass
        time.sleep(0.3)
    raise AssertionError("disposable-gateway-not-ready")


def name(base, run_id):
    return "nexus-p05-" + base + "-" + run_id


def gateway_start(container, storage, port, token):
    run("docker", "run", "-d", "--name", container,
        "--publish", f"127.0.0.1:{port}:3000",
        "--env", "NEXUS_API_TOKEN=" + token,
        "--env", "NEXUS_DATA_DIR=/data",
        "--env", "NEXUS_BIND_ADDR=0.0.0.0:3000",
        "--mount", "type=bind,source=" + str(storage) + ",target=/data",
        IMAGE, timeout=60)


def gateway_stop(container, *, remove=True):
    run("docker", "stop", "-t", "8", container, timeout=30)
    if remove:
        run("docker", "rm", container, timeout=30)


def test_pure_contract():
    good = {"schema_version": 1, "workspace": {"id": "synthetic"}}
    require(len(sha_json(good)) == 64, "digest-shape")
    require(sha_json(good) == sha_json({"workspace": {"id": "synthetic"},
                                       "schema_version": 1}), "canonical-digest")
    for illegal in ("https://example.org", "/v1/requests?token=bad",
                    "//wronghost/readyz", "/v1/workspaces/../bad"):
        require(not safe_path(illegal), "nonlocal-http-disallowed")
    print(json.dumps({"scope": "pure-local-validation",
                      "status": "PASS", "checks": 3}))


def main():
    if "--self-test" in sys.argv:
        test_pure_contract()
        return
    runid = os.environ.get("GITHUB_RUN_ID", "")
    require(os.environ.get("GITHUB_ACTIONS") == "true", "ci-only")
    require(os.environ.get("NEXUS_P05_DISPOSABLE") == "true", "disposable-only")
    require(re.fullmatch(r"[0-9]{1,15}", runid) is not None, "invalid-run-id")
    require(not any(os.getenv(k) for k in (
        "RAILWAY_TOKEN", "RAILWAY_API_TOKEN",
        "NEXUS_API_TOKEN", "RENDER_API_KEY")), "production-credentials-prohibited")
    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve()
    require(runner_temp.is_dir() and not runner_temp.is_relative_to(HERE.parent),
            "no-private-runner-temp")
    scratch = Path(tempfile.mkdtemp(
        prefix="nexus-p05-disposable-", dir=runner_temp))
    require(not scratch.is_relative_to(HERE.parent), "private-temp-in-repository")
    source = scratch / "primary-store"
    source.mkdir(mode=0o700)
    copied = scratch / "offhost-cold-copy"
    copied.mkdir(mode=0o700)
    recovered = scratch / "separate-restore-store"
    archive = scratch / "private-synthetic-archive.json"
    token = secrets.token_urlsafe(48)
    port = 20000 + int(runid[-4:])
    source_name = name("source", runid)
    recovery_name = name("recovery", runid)
    containers = [source_name, recovery_name]
    phase = "startup"
    report_file = Path(REPORT_NAME).absolute()
    require(not report_file.exists(), "report-already-exists")
    try:
        gateway_start(source_name, source, port, token)
        ready(port, 200)
        phase = "source-state"
        status, first = http(port, "POST", "/v1/workspaces", token, {
            "workspace_id": "pilot05-synthetic",
            "question": "Can an isolated copy preserve evidence and judgment?",
            "provenance_id": "synthetic:pilot05"})
        require(status == 201 and first["workspace"]["judgment"] is None,
                "initial-judgment-not-empty")
        status, claim = http(port, "POST",
                             "/v1/workspaces/pilot05-synthetic/claims", token, {
            "text": "Machine notes are not a human decision",
            "origin": {"kind": "external_evidence",
                       "source": "fixture:synthetic"},
            "uncertainty": "high",
            "provenance_id": "synthetic:source"})
        require(status == 200 and claim["workspace"]["judgment"] is None,
                "claim-generated-judgment")
        status, alt = http(port, "POST",
                          "/v1/workspaces/pilot05-synthetic/alternatives", token, {
            "label": "Inspect first",
            "consequences": ["Only a synthetic decision"],
            "provenance_id": "synthetic:alternative"})
        require(status == 200 and alt["workspace"]["judgment"] is None,
                "alternative-generated-judgment")
        status, judgment = http(port, "POST",
                               "/v1/workspaces/pilot05-synthetic/judgment", token, {
            "decision": "Explicit human-like fixture selection",
            "rationale": "Only test replay boundary",
            "provenance_id": "synthetic:human"})
        require(status == 200 and judgment["workspace"]["judgment"]["decision"] ==
                "Explicit human-like fixture selection", "judgment-not-explicit")
        request_id = "pilot05-request-" + runid
        status, pending = http(port, "POST", "/v1/requests", token, {
            "request_id": request_id, "authority": "user", "action": "present",
            "value": "synthetic-data", "payload": "opaque"})
        require(status == 202 and pending["status"] == "pending",
                "request-not-accepted")
        status, before = http(port, "GET",
                              "/v1/workspaces/pilot05-synthetic", token)
        require(status == 200 and len(before["events"]) >= 4,
                "incomplete-workspace")
        before_hash = sha_json(before)
        status, q = http(port, "GET", "/v1/requests/" + request_id, token)
        require(status == 200 and q["status"] == "pending", "ledger-unreadable")
        gateway_stop(source_name, remove=False)

        phase = "cold-copy"
        # Freeze writers before copying; Docker reads the stopped instance's
        # mounted store and copies bytes OUT to a separate runner directory.
        run("docker", "cp", source_name + ":/data/.", str(copied), timeout=75)
        # The primary container is now absent. Do not mount its store again.
        run("docker", "rm", "-f", source_name)
        source.rename(scratch / "unavailable-primary-store")
        require(not source.exists(), "source-not-isolated")
        require((copied / "requests").is_dir(), "request-ledger-copy-missing")

        phase = "snapshot-and-tamper"
        phase = "snapshot-backup"
        run(sys.executable, SNAPSHOT, "backup", copied, archive, "--offline")
        phase = "snapshot-parse"
        raw = json.loads(archive.read_text())
        require(raw["schema"] == "nexus.data-snapshot.v1", "snapshot-schema")
        require(raw["authority"] == "none", "snapshot-no-authority")
        phase = "snapshot-tamper-reject"
        bad_archive = scratch / "damaged-snapshot.json"
        invalid = json.loads(archive.read_text())
        require(bool(invalid["files"]), "empty-backup")
        invalid["files"][0]["sha256"] = "0" * 64
        bad_archive.write_text(json.dumps(invalid))
        forbidden_target = scratch / "forbidden-restore"
        bad = subprocess.run(
            [sys.executable, str(SNAPSHOT), "restore", str(bad_archive),
             str(forbidden_target), "--offline"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=40)
        require(bad.returncode != 0 and not forbidden_target.exists(),
                "corrupt-snapshot-restored")
        phase = "restore-new-root"
        # Ownership is preserved for unprivileged runtime UID 10001.
        run("sudo", sys.executable, SNAPSHOT, "restore", archive,
            recovered, "--offline", "--owner", "10001:10001", timeout=45)
        phase = "check-quarantine-root-ownership"
        # The restored directory is deliberately 0700 and belongs to UID 10001.
        # Reading it as the CI runner is correctly denied; check file presence
        # with privileged test, then let the unprivileged gateway handle data.
        run("sudo", "test", "-f", recovered / ".nexus-recovery-required")

        phase = "quarantined-gateway"
        gateway_start(recovery_name, recovered, port, token)
        ready(port, 503)
        status, restored = http(port, "GET",
                                "/v1/workspaces/pilot05-synthetic", token)
        require(status == 200 and sha_json(restored) == before_hash,
                "separate-restored-data-mismatch")
        status, replay = http(port, "GET", "/v1/requests/" + request_id, token)
        require(status == 200 and replay["status"] == "pending",
                "restored-request-ledger-mismatch")
        status, _ = http(port, "POST", "/v1/requests", token, {
            "request_id": request_id + "-new", "authority": "user",
            "action": "present", "value": "synthetic", "payload": "opaque"})
        require(status == 503, "quarantined-write-not-blocked")
        status, _ = http(port, "GET",
                         "/v1/workspaces/pilot05-synthetic")
        require(status == 401, "quarantine-allowed-anonymous-workspace")
        gateway_stop(recovery_name)

        phase = "explicit-synthetic-resume"
        run("sudo", sys.executable, SNAPSHOT, "resume", recovered,
            "--offline", "--acknowledge-replay-risk", timeout=45)
        gateway_start(recovery_name, recovered, port, token)
        ready(port, 200)
        status, resumed = http(port, "GET",
                               "/v1/workspaces/pilot05-synthetic", token)
        require(status == 200 and sha_json(resumed) == before_hash,
                "resumed-snapshot-mismatch")
        for key in (None, "incorrect-fixture-token"):
            status, _ = http(port, "GET",
                             "/v1/workspaces/pilot05-synthetic", key)
            require(status == 401, "authentication-boundary-failed")
        status, conflict = http(port, "POST", "/v1/requests", token, {
            "request_id": request_id, "authority": "user",
            "action": "present", "value": "synthetic", "payload": "opaque"})
        require(status == 409, "replay-protection-lost")
        status, _ = http(port, "POST", "/v1/requests", token, {
            "request_id": request_id + "-new", "authority": "user",
            "action": "present", "value": "synthetic", "payload": "opaque"})
        require(status == 202, "new-request-not-accepted")

        phase = "third-process"
        gateway_stop(recovery_name)
        gateway_start(recovery_name, recovered, port, token)
        ready(port, 200)
        status, final = http(port, "GET",
                             "/v1/workspaces/pilot05-synthetic", token)
        require(status == 200 and sha_json(final) == before_hash,
                "restart-changed-restored-snapshot")
        status, new_record = http(port, "GET",
                                  "/v1/requests/" + request_id + "-new", token)
        require(status == 200 and new_record["status"] == "pending",
                "new-request-not-durable")
        report = {
            "schema": "nexus.pilot05.synthetic-cross-store.v1",
            "status": "PASS_SYNTHETIC_CROSS_STORE_RECOVERY",
            "scope": "two-distinct-disposable-docker-containers-same-ci-runner",
            "source_writes_stopped_before_copy": True,
            "source_storage_not_mounted_on_restored_container": True,
            "cold_external_directory_copy": True,
            "corrupt_archive_rejected": True,
            "full_archive_restored_to_separate_storage": True,
            "restore_quarantined_before_resume": True,
            "authenticated_data_hash_preserved": True,
            "request_ledger_preserved": True,
            "unauthenticated_access_rejected": True,
            "replay_prevention_preserved": True,
            "fresh_request_survived_container_restart": True,
            "synthetic_workspace_sha256": before_hash,
            "synthetic_archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "production_volume_read": False,
            "railway_access_used": False,
            "external_host_independence_proven": False,
            "production_consistency_proven": False,
            "production_backup_proven": False,
            "production_restore_proven": False,
            "human_authentication_tested": False,
            "seal": False,
            "authority": "none",
        }
        with report_file.open("x") as f:
            json.dump(report, f, indent=2, sort_keys=True)
            f.write("\n")
        print("PILOT 05: SYNTHETIC CROSS-STORE HTTP RECOVERY PASS")
    except Exception as error:
        # Only deterministic phase + error class, never tokens or data.
        print("PILOT 05 BLOCKED phase=" + phase +
              " error=" + type(error).__name__, file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        for container in containers:
            subprocess.run(["docker", "rm", "-f", container],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           check=False, timeout=25)
        # The CI runner itself is ephemeral. Never recursively erase an
        # operator path: this scratch dir was created in RUNNER_TEMP by this run.


if __name__ == "__main__":
    main()
