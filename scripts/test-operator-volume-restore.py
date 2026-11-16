#!/usr/bin/env python3
"""CI-only real Docker volume-loss & operator receipt restore drill.

Two distinct no-network, unprivileged containers run on one disposable Docker
host. Three named volumes hold source state, transferred backup and restored
state. Source state volume is deleted BEFORE restore; no production data.
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
import subprocess
import sys

SENTINEL = b"NEXUS_P28_SENTINEL_v1"
DIGEST = hashlib.sha256(b"NEXUS_P28_SINGLE_USE_APPROVAL").hexdigest()
IMAGE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:/-]*@sha256:[0-9a-f]{64}$")


def code_imports():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "nexus-cloud"))
    from agent_workspace import Workspace, WorkspaceDenied
    from agent_journal import ApprovalJournal
    return Workspace, WorkspaceDenied, ApprovalJournal


def fixture() -> None:
    Workspace, WorkspaceDenied, ApprovalJournal = code_imports()
    root = Path("/state")
    ws = Workspace(root, "acceptance")
    with ws.operation_lock():
        ws.write("input.txt", b"NEXUS_P28_INPUT_v1")
        journal = ApprovalJournal(ws)
        journal.claim(DIGEST, version=3, workspace_before=ws.manifest()["sha256"],
                      execution_nonce="a" * 32)
        ws.write("result.txt", SENTINEL)
        record = journal.finish(DIGEST, status="complete",
                                workspace_after=ws.manifest()["sha256"],
                                completed_steps=2,
                                step_summaries=[{"tool": "verify_sha256", "status": "complete"},
                                                {"tool": "write", "status": "complete"}])
        assert record["state"] == "finished"
        assert journal.audit()["status"] == "clear"
    print(json.dumps({"status": "synthetic-source-state-created",
                      "finished_receipts": 1, "production_ready": False}))


def check_restored() -> None:
    Workspace, WorkspaceDenied, ApprovalJournal = code_imports()
    root = Path("/state")
    ws = Workspace(root, "acceptance")
    with ws.operation_lock():
        assert ws.read("result.txt") == SENTINEL
        assert ws.read("input.txt") == b"NEXUS_P28_INPUT_v1"
        journal = ApprovalJournal(ws)
        assert journal.audit()["status"] == "clear"
        record = journal.read(DIGEST)
        assert record["state"] == "finished"
        assert record["result"] == "complete"
        assert record["completed_steps"] == 2
        assert record["workspace_sha256_after"] == ws.manifest()["sha256"]
        try:
            journal.claim(DIGEST, version=3,
                          workspace_before=record["workspace_sha256_before"],
                          execution_nonce="a" * 32)
        except WorkspaceDenied as exc:
            assert "approval-already-consumed" in str(exc)
        else:
            raise AssertionError("restored-approval-was-replayed")
    assert not (root / ".nexus-operator.token").exists()
    assert not (root / ".nexus-operator.sock").exists()
    print(json.dumps({"status": "restored-journal-replay-denied",
                      "workspace_integrity": True,
                      "no_automatic_execution": True, "production_ready": False}))


def make_corrupt_copy() -> None:
    source = Path("/backup/snapshot.zip")
    target = Path("/backup/corrupt.zip")
    payload = bytearray(source.read_bytes())
    index = payload.find(SENTINEL)
    if index < 0:
        raise RuntimeError("known-synthetic-marker-missing")
    payload[index] ^= 1
    with target.open("xb") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    print(json.dumps({"status": "tampered-snapshot-created",
                      "tampered_sha256": hashlib.sha256(payload).hexdigest()}))


def call(*args, expect=0, timeout=120) -> str:
    completed = subprocess.run([str(arg) for arg in args], capture_output=True,
                               text=True, timeout=timeout, check=False)
    if (expect == 0 and completed.returncode != 0) or (
            expect != 0 and completed.returncode == 0):
        raise RuntimeError("docker-drill-command-failed:" +
                           " rc=" + str(completed.returncode) +
                           " stderr-tail=" + completed.stderr[-450:])
    return completed.stdout


def docker(*args, expect=0, timeout=120) -> str:
    return call("docker", *args, expect=expect, timeout=timeout)


def run(image: str, volumes: list[str], *argv: str, expect=0) -> str:
    args = ["run", "--rm", "--network", "none", "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m", "--pids-limit", "64",
            "--memory", "256m", "--cpus", "1",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--user", "10001:10001"]
    for volume in volumes:
        args += ["-v", volume]
    args += ["-v", str(Path(__file__).resolve().parent.parent) + ":/opt/nexus:ro"]
    return docker(*args, image, "python3", "-I", "-B", *argv, expect=expect)


def init_volume(image: str, name: str, mount: str) -> None:
    docker("run", "--rm", "--network", "none", "--read-only",
           "--cap-drop", "ALL", "--cap-add", "CHOWN", "--cap-add", "FOWNER",
           "--security-opt", "no-new-privileges",
           "-v", name + ":" + mount, image, "python3", "-c",
           "import os; os.chown(" + repr(mount) + ",10001,10001);"
           " os.chmod(" + repr(mount) + ",0o700)")


def no_restore_tree(image: str, state: str, backup: str) -> None:
    result = run(image, [state + ":/state", backup + ":/backup:ro"],
                 "-c", "import os,json; print(json.dumps(sorted(os.listdir('/state'))))")
    if json.loads(result) != []:
        raise RuntimeError("denied-restore-created-state")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", nargs="?", choices=["fixture", "restored-check", "corrupt"])
    p.add_argument("--image", default=None)
    args = p.parse_args()
    if args.action == "fixture":
        fixture()
        return 0
    if args.action == "restored-check":
        check_restored()
        return 0
    if args.action == "corrupt":
        make_corrupt_copy()
        return 0
    if not args.image or not IMAGE_RE.fullmatch(args.image):
        raise SystemExit("CI requires exact Docker image digest")
    if sys.platform != "linux" or os.getuid() == 0:
        raise SystemExit("nonroot Linux Docker CI only")
    image = args.image
    suffix = secrets.token_hex(8)
    source = "nexus-p28-source-" + suffix
    backup = "nexus-p28-transfer-" + suffix
    restored = "nexus-p28-restored-" + suffix
    volumes = [source, backup, restored]
    try:
        for v in volumes:
            docker("volume", "create", v)
        for name, mount in ((source, "/state"), (backup, "/backup"),
                            (restored, "/state")):
            init_volume(image, name, mount)
        fixture_report = run(image, [source + ":/state"],
                             "/opt/nexus/scripts/test-operator-volume-restore.py", "fixture")
        assert json.loads(fixture_report)["status"] == "synthetic-source-state-created"
        export_report = run(image, [source + ":/state", backup + ":/backup"],
                            "/opt/nexus/scripts/nexus-operator-snapshot.py", "export",
                            "--root", "/state", "--workspace", "acceptance",
                            "--archive", "/backup/snapshot.zip", "--approve-offline-export")
        evidence = json.loads(export_report)
        assert evidence["status"] == "offline-snapshot-created"
        assert evidence["finished_count"] == 1
        expected = evidence["snapshot_sha256"]

        # Destroy source volume BEFORE any recovery. Both data and journal are gone.
        docker("volume", "rm", source)
        volumes.remove(source)

        run(image, [restored + ":/state", backup + ":/backup:ro"],
            "/opt/nexus/scripts/nexus-operator-snapshot.py", "restore",
            "--root", "/state", "--workspace", "acceptance",
            "--archive", "/backup/snapshot.zip",
            "--expected-sha256", "0" * 64, "--approve-offline-restore", expect=2)
        no_restore_tree(image, restored, backup)

        corrupt_report = run(image, [backup + ":/backup"],
                             "/opt/nexus/scripts/test-operator-volume-restore.py",
                             "corrupt")
        changed_sha = json.loads(corrupt_report)["tampered_sha256"]
        run(image, [restored + ":/state", backup + ":/backup:ro"],
            "/opt/nexus/scripts/nexus-operator-snapshot.py", "restore",
            "--root", "/state", "--workspace", "acceptance",
            "--archive", "/backup/corrupt.zip",
            "--expected-sha256", changed_sha,
            "--approve-offline-restore", expect=2)
        no_restore_tree(image, restored, backup)

        restore_report = run(image, [restored + ":/state", backup + ":/backup:ro"],
                             "/opt/nexus/scripts/nexus-operator-snapshot.py", "restore",
                             "--root", "/state", "--workspace", "acceptance",
                             "--archive", "/backup/snapshot.zip",
                             "--expected-sha256", expected,
                             "--approve-offline-restore")
        restored_evidence = json.loads(restore_report)
        assert restored_evidence["status"] == "offline-snapshot-restored-not-executed"
        assert restored_evidence["workspace_sha256"] == evidence["workspace_sha256"]
        check = run(image, [restored + ":/state"],
                    "/opt/nexus/scripts/test-operator-volume-restore.py",
                    "restored-check")
        assert json.loads(check)["status"] == "restored-journal-replay-denied"
        run(image, [restored + ":/state", backup + ":/backup:ro"],
            "/opt/nexus/scripts/nexus-operator-snapshot.py", "restore",
            "--root", "/state", "--workspace", "acceptance",
            "--archive", "/backup/snapshot.zip",
            "--expected-sha256", expected,
            "--approve-offline-restore", expect=2)
        print(json.dumps({"schema": "nexus.operator.two-volume-recovery.v1",
                          "status": "isolated-volume-loss-restore-passed",
                          "source_volume_destroyed_before_restore": True,
                          "distinct_backup_and_restore_volumes": True,
                          "backup_integrity_pin_matched": True,
                          "tampered_payload_denied_even_with_matching_archive_hash": True,
                          "untrusted_digest_denied_before_restore": True,
                          "journal_finished_receipt_restored": True,
                          "original_plan_replay_denied": True,
                          "overwriting_restored_root_denied": True,
                          "real_independent_provider_attested": False,
                          "same_docker_host_controls_both_containers": True,
                          "production_ready": False, "authority": "none"},
                         sort_keys=True))
        return 0
    finally:
        # Never delete host-side user resources. Names are random disposable
        # test-owned Docker volumes; cleanup even if an assertion fails.
        for volume in reversed(volumes):
            docker("volume", "rm", "-f", volume)


if __name__ == "__main__":
    raise SystemExit(main())
