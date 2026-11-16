#!/usr/bin/env python3
"""Phase 29: cross-runner synthetic-only offline backup and anti-replay drill.

This script is a CI test harness, NOT a production backup service. Only known
constant synthetic bytes and a finished synthetic approval may be exported.
No network, secrets, user files, browsers, model tools or automatic approvals.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "nexus-cloud"))
from agent_workspace import Workspace, WorkspaceDenied
from agent_journal import ApprovalJournal

SOURCE = Path(__file__).resolve().parent / "nexus-operator-snapshot.py"
SPEC = importlib.util.spec_from_file_location("nexus_cross_runner_snapshot", SOURCE)
if SPEC is None or SPEC.loader is None:
    raise SystemExit("snapshot-source-unavailable")
snapshot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(snapshot)

SCHEMA = "nexus.operator.cross-runner-recovery.v1"
WORKSPACE = "acceptance"
INPUT = b"NEXUS_CROSS_RUNNER_SYNTHETIC_INPUT_V1"
OUTPUT = b"NEXUS_CROSS_RUNNER_SYNTHETIC_RESULT_V1"
DIGEST = hashlib.sha256(b"NEXUS_CROSS_RUNNER_CONSUMED_APPROVAL_V1").hexdigest()
MAX_SNAPSHOT_BYTES = 4 * 1024 * 1024


def preflight_scratch(root: Path) -> Path:
    if (os.name != "posix" or not sys.platform.startswith("linux")
            or os.getuid() == 0 or not root.is_absolute()
            or ".." in root.parts or root.is_symlink()):
        raise WorkspaceDenied("cross-runner-needs-nonroot-private-absolute-scratch")
    st = root.stat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise WorkspaceDenied("cross-runner-unsafe-scratch")
    if any(root.iterdir()):
        raise WorkspaceDenied("cross-runner-scratch-must-be-empty")
    return root


def _new_private(root: Path, name: str) -> Path:
    path = root / name
    path.mkdir(mode=0o700)
    return path


def produce(scratch: Path) -> dict:
    preflight_scratch(scratch)
    source_root = _new_private(scratch, "source")
    export_root = _new_private(scratch, "transfer")
    ws = Workspace(source_root, WORKSPACE)
    with ws.operation_lock():
        ws.write("input.txt", INPUT)
        journal = ApprovalJournal(ws)
        journal.claim(DIGEST, version=3, workspace_before=ws.manifest()["sha256"],
                      execution_nonce="d" * 32)
        ws.write("result.txt", OUTPUT)
        receipt = journal.finish(DIGEST, status="complete",
                                 workspace_after=ws.manifest()["sha256"],
                                 completed_steps=2,
                                 step_summaries=[{"index": 0, "tool": "verify_sha256", "status": "completed"},
                                                 {"index": 1, "tool": "write", "status": "completed"}])
        if receipt["state"] != "finished":
            raise WorkspaceDenied("synthetic-approval-not-finished")
    export_path = export_root / "snapshot.zip"
    evidence = snapshot.export(source_root, WORKSPACE, export_path)
    if (evidence["status"] != "offline-snapshot-created"
            or evidence["finished_count"] != 1
            or evidence["file_count"] != 2
            or export_path.stat().st_size > MAX_SNAPSHOT_BYTES):
        raise WorkspaceDenied("synthetic-snapshot-not-verifiable")
    if evidence["workspace_sha256"] != ws.manifest()["sha256"]:
        raise WorkspaceDenied("synthetic-source-manifest-drift")
    # The SOURCE root has no after-life on the receiver runner. The archive
    # is transferred by the workflow artifact service, never a host volume.
    return {"schema": SCHEMA, "status": "cross-runner-synthetic-exported",
            "snapshot_sha256": evidence["snapshot_sha256"],
            "workspace_sha256": evidence["workspace_sha256"],
            "finished_count": 1, "synthetic_only": True,
            "publisher_authenticated": False,
            "same_host_restore": False, "production_ready": False,
            "authority": "none"}


def _checked_archive_file(path: Path, expected: str) -> None:
    if not path.is_absolute() or path.is_symlink():
        raise WorkspaceDenied("cross-runner-unsafe-archive")
    # This verifies before any restore mutation; snapshot.restore repeats
    # a bounded no-follow fd read of exactly the same archive digest.
    raw = snapshot.checked_archive(path, expected)
    if len(raw) > MAX_SNAPSHOT_BYTES:
        raise WorkspaceDenied("cross-runner-oversize-synthetic-snapshot")


def _must_reject(fn, reason: str):
    try:
        fn()
    except (WorkspaceDenied, OSError, ValueError, zipfile.BadZipFile):
        return
    raise WorkspaceDenied(reason)


def receive(scratch: Path, archive: Path, expected_sha: str,
            expected_workspace_sha: str) -> dict:
    preflight_scratch(scratch)
    if (not snapshot.SHA.fullmatch(expected_workspace_sha)
            or not snapshot.SHA.fullmatch(expected_sha)):
        raise WorkspaceDenied("cross-runner-expected-sha-required")
    _checked_archive_file(archive, expected_sha)
    # Validate independently supplied workspace SHA and full internal ZIP
    # manifest BEFORE creating the destination root or restoring any file.
    archive_raw = snapshot.checked_archive(archive, expected_sha)
    metadata, _, _ = snapshot.validate(archive_raw, WORKSPACE)
    if metadata["workspace_sha256"] != expected_workspace_sha:
        raise WorkspaceDenied("cross-runner-workspace-pin-mismatch")
    restored_root = _new_private(scratch, "restored")

    # Negative 1: a wrong digest fails before creating the workspace.
    _must_reject(lambda: snapshot.restore(
        restored_root, WORKSPACE, archive, "0"*64
        if expected_sha != "0"*64 else "1"*64), "cross-runner-wrong-sha-accepted")
    if any(restored_root.iterdir()):
        raise WorkspaceDenied("cross-runner-wrong-sha-modified-root")

    # Negative 2: mutate the *synthetic* source ZIP and pin the new ZIP hash.
    # This must be rejected by inner content hashes before any writes.
    corrupt_root = _new_private(scratch, "corrupt-transfer")
    modified = corrupt_root / "mutated.zip"
    content = bytearray(archive.read_bytes())
    index = content.find(OUTPUT)
    if index < 0:
        raise WorkspaceDenied("cross-runner-synthetic-sentinel-absent")
    content[index] ^= 1
    with modified.open("xb") as dst:
        dst.write(content)
        dst.flush()
        os.fsync(dst.fileno())
    modified.chmod(0o600)
    mutated_digest = hashlib.sha256(content).hexdigest()
    _must_reject(lambda: snapshot.restore(
        restored_root, WORKSPACE, modified, mutated_digest),
        "cross-runner-mutated-inner-bytes-accepted")
    if any(restored_root.iterdir()):
        raise WorkspaceDenied("cross-runner-mutated-snapshot-modified-root")

    result = snapshot.restore(restored_root, WORKSPACE, archive, expected_sha)
    if (result.get("status") != "offline-snapshot-restored-not-executed"
            or result.get("workspace_sha256") != expected_workspace_sha
            or result.get("finished_count") != 1
            or result.get("file_count") != 2
            or result.get("jobs_restarted") is not False
            or result.get("publisher_authenticated") is not False):
        raise WorkspaceDenied("cross-runner-restore-report-mismatch")
    ws = Workspace(restored_root, WORKSPACE)
    with ws.operation_lock():
        if (ws.read("input.txt") != INPUT or ws.read("result.txt") != OUTPUT
                or ws.manifest()["sha256"] != expected_workspace_sha):
            raise WorkspaceDenied("cross-runner-restored-workspace-mismatch")
        ledger = ApprovalJournal(ws)
        record = ledger.read(DIGEST)
        if (record["state"] != "finished" or record["result"] != "complete"
                or record["completed_steps"] != 2
                or record.get("workspace_sha256_after") != expected_workspace_sha):
            raise WorkspaceDenied("cross-runner-restored-receipt-mismatch")
        _must_reject(
            lambda: ledger.claim(
                DIGEST, version=3, workspace_before=record["workspace_sha256_before"],
                execution_nonce="d"*32),
            "cross-runner-consumed-approval-replayed")
        if ledger.read(DIGEST) != record:
            raise WorkspaceDenied("cross-runner-ledger-mutated-by-replay-attempt")
    # Negative 3: second import may not overwrite previously recovered state.
    _must_reject(
        lambda: snapshot.restore(restored_root, WORKSPACE, archive, expected_sha),
        "cross-runner-restore-overwrite-accepted")
    if not (restored_root / WORKSPACE / "result.txt").is_file():
        raise WorkspaceDenied("cross-runner-overwrite-destroyed-data")
    if any((restored_root / name).exists() for name in
           (".nexus-operator.token", ".nexus-operator.sock")):
        raise WorkspaceDenied("cross-runner-transport-secret-restored")
    return {
        "schema": SCHEMA,
        "status": "cross-runner-synthetic-restore-passed",
        "snapshot_sha256_matched": True,
        "workspace_sha256_matched": True,
        "synthetic_only": True,
        "restored_finished_receipt": True,
        "original_approval_replay_denied": True,
        "wrong_archive_digest_denied": True,
        "tampered_content_with_new_digest_denied": True,
        "overwrite_restored_root_denied": True,
        "transport_credentials_absent": True,
        "jobs_restarted": False,
        "distinct_github_jobs_required": True,
        "independent_provider_attested": False,
        "publisher_authenticated": False,
        "backup_encrypted": False,
        "production_ready": False,
        "authority": "none",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("produce", "receive"))
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--expected-workspace-sha256")
    parser.add_argument("--approve-synthetic-ci", action="store_true")
    options = parser.parse_args(argv)
    try:
        if options.approve_synthetic_ci is not True:
            raise WorkspaceDenied("synthetic-ci-approval-required")
        if options.action == "produce":
            if options.archive or options.expected_sha256 or options.expected_workspace_sha256:
                raise WorkspaceDenied("synthetic-produce-arguments")
            result = produce(options.scratch)
        else:
            if not options.archive or not options.expected_sha256 or not options.expected_workspace_sha256:
                raise WorkspaceDenied("synthetic-receive-arguments")
            result = receive(options.scratch, options.archive, options.expected_sha256,
                             options.expected_workspace_sha256)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, WorkspaceDenied, ValueError, KeyError, AssertionError) as exc:
        print(json.dumps({"status": "denied", "reason": type(exc).__name__,
                          "authority": "none", "production_ready": False}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
