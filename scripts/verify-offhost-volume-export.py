#!/usr/bin/env python3
"""Private, offline intake for a COPIED Railway NEXUS data directory.

This never reads Railway directly. Operator-supplied origin metadata is not
verified. Success means structural integrity and isolated byte round-trip only,
NOT that the production volume has been backed up or is recoverable.
Never store output in a public checkout or CI artifact.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import stat
import subprocess
import sys
import os

SCRIPT = Path(__file__).with_name("data-snapshot.py")
spec = importlib.util.spec_from_file_location("nexus_data_snapshot", SCRIPT)
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)
REPO = Path(__file__).resolve().parent.parent


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def valid_origin(directory):
    directory = directory.absolute()
    require(directory == directory.resolve(), "symlinked path not allowed")
    require(directory.is_dir() and not directory.is_symlink(), "source must be a real directory")
    return directory


def local_copy_manifest(source):
    """Bounded read-only manifest of exact copied NEXUS file layout.

    This is a *local* copy stability observation, not a Railway
    point-in-time snapshot. Never return file names, hashes or user text in
    logs, published artifacts or user-facing receipts.
    """
    request_dir = source / "requests"
    require(request_dir.is_dir() and not request_dir.is_symlink(),
            "private copy must contain a regular request ledger directory")
    files = []
    for entry in source.iterdir():
        if entry.name == "requests":
            files.extend(request_dir.iterdir())
        else:
            files.append(entry)
    require(len(files) <= snapshot.MAX_FILES, "copied file limit exceeded")
    total = 0
    entries = {}
    for path in sorted(files):
        name = path.relative_to(source).as_posix()
        content = snapshot.read_regular(path, snapshot.MAX_BYTES - total)
        total += len(content)
        snapshot.validate_file(name, content)
        entries[name] = (len(content), hashlib.sha256(content).hexdigest())
    require(len(entries) == len(files), "duplicate copied paths")
    return entries


def verify_quarantined_restore(restored, expected):
    """Reject post-restore drift, including directory layout and quarantine bytes.

    Called after isolated restore and again after the optional operator-supplied
    Rust subprocess, whose exit code cannot certify that the input remains
    unchanged. All file bytes and markers are private.
    """
    actual_dirs = set()
    actual_names = set()
    for index, path in enumerate(restored.rglob("*")):
        require(index < snapshot.MAX_FILES + 2, "isolated restore file count exceeded")
        name = path.relative_to(restored).as_posix()
        require(not path.is_symlink(), "isolated restored tree contains symlink")
        if path.is_dir():
            actual_dirs.add(name)
        else:
            actual_names.add(name)
    require(actual_dirs == {"requests"}, "isolated restored directory layout differs")
    require(actual_names == set(expected) | {snapshot.RECOVERY_MARKER},
            "isolated restored file set differs from archived data")
    for name, data in expected.items():
        require(snapshot.read_regular(restored / name, snapshot.MAX_BYTES) == data,
                "isolated restored data differs from archive")
    require(snapshot.read_regular(restored / snapshot.RECOVERY_MARKER,
                                  len(snapshot.RECOVERY_BYTES)) == snapshot.RECOVERY_BYTES,
            "restore quarantine is missing")

def run(args):
    source = valid_origin(args.export_root)
    output = args.private_evidence_dir.absolute()
    uuid = r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"
    require(re.fullmatch(uuid, args.volume_id) is not None, "invalid volume identifier")
    require(re.fullmatch(uuid, args.deployment_id) is not None, "invalid deployment identifier")
    require(re.fullmatch(r"[0-9a-f]{40}", args.runtime_commit) is not None, "invalid runtime commit")
    require(not output.exists() and not output.is_symlink(), "evidence directory must not exist")
    require(output.parent.is_dir() and output.parent == output.parent.resolve(),
            "evidence parent must be a real directory")
    require(not output.is_relative_to(source) and not source.is_relative_to(output),
            "evidence must be separate from the exported directory")
    require(not output.is_relative_to(REPO), "private snapshot must not enter a public checkout")
    require(not source.is_relative_to(REPO), "exported data must not enter a public checkout")

    output.mkdir(mode=0o700)
    archive = output / "nexus-private-data-snapshot.json"
    # Distinguish a stable *local* copy from an internally consistent
    # archive made from a copy that was still being changed. Three
    # independent reads (before, snapshot, after) must agree by exact
    # name, size and SHA-256, including request markers.
    before = local_copy_manifest(source)
    snapshot.backup(source, archive)
    archive_records = snapshot.validated_records(archive)
    archive_sha_before_audit = hashlib.sha256(archive.read_bytes()).hexdigest()
    inside_archive = {
        name: (len(data), hashlib.sha256(data).hexdigest())
        for name, data in archive_records
    }
    require(before == inside_archive,
            "copied data changed before or during archive construction")
    inspection = snapshot.inspect_snapshot(archive)
    restored = output / "isolated-restore-rehearsal"
    snapshot.restore(archive, restored)
    expected = dict(snapshot.validated_records(archive))
    expected.pop(snapshot.RECOVERY_MARKER, None)
    verify_quarantined_restore(restored, expected)
    after = local_copy_manifest(source)
    require(after == before == inside_archive,
            "copied data changed while validating the isolated restore")
    core_audit = "not_evaluated"
    core_binary_identity = "not_verified"
    rust_validator = getattr(args, "rust_validator_bin", None)
    if rust_validator is not None:
        rust_validator = rust_validator.absolute()
        require(rust_validator.is_file() and not rust_validator.is_symlink()
                and os.access(rust_validator, os.X_OK),
                "private Rust audit executable unavailable")
        require(rust_validator.parent == rust_validator.parent.resolve(),
                "Rust audit executable directory is not canonical")
        try:
            result = subprocess.run(
                [str(rust_validator), str(restored)],
                cwd=output,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=90, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise ValueError("private Rust core audit failed") from None
        require(result.returncode == 0, "private Rust core audit rejected copied data")
        # A validator executes between the earlier copy/restore checks and
        # receipt creation. Catch any source or quarantine drift in that gap
        # before issuing success. This remains a bounded local observation,
        # not proof of atomic Railway capture or a trusted Rust binary.
        require(local_copy_manifest(source) == before == inside_archive,
                "copied data changed during private Rust audit")
        verify_quarantined_restore(restored, expected)
        core_audit = "pass_operator_supplied_rust_binary"
        core_binary_identity = "operator_supplied_unverified"
    # Verify exact archive identity at receipt time in BOTH structural-only
    # and optional Rust modes; never report a stale pre-audit digest.
    archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    require(archive_sha == archive_sha_before_audit,
            "private archive changed during private intake")
    # A missing Rust binary is never silently reported as an audit PASS.
    report = {
        "schema": "nexus.offhost-volume-intake.v1",
        "status": "STRUCTURAL_REHEARSAL_PASS",
        "volume_id": args.volume_id,
        "deployment_id": args.deployment_id,
        "runtime_commit": args.runtime_commit,
        "provider_identity": "operator_supplied_unverified",
        "copy_provenance": "unverified",
        "production_volume_contents": "not_directly_observed",
        "source_consistency": "not_verified",
        "local_copy_scans_matched_archive": True,
        "local_copy_check": "before_archive_and_after_restored_bytes",
        "rust_core_audit": core_audit,
        "rust_core_binary_identity": core_binary_identity,
        "post_rust_source_archive_and_restore_rechecked": rust_validator is not None,
        "independent_railway_backup": "not_proven",
        "live_survival": "not_evaluated",
        "live_recovery": "not_evaluated",
        "file_count": inspection["file_count"],
        "snapshot_sha256": archive_sha,
        "isolated_byte_roundtrip": True,
        "restored_quarantined": True,
        "authority": "none",
    }
    path = output / "intake-report.json"
    with path.open("x", encoding="utf-8") as f:
        json.dump(report, f, sort_keys=True, indent=2)
        f.write("\n")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    print("OFFHOST COPY STRUCTURAL REHEARSAL: PASS (local-copy scans match; Rust audit status in private report; Railway origin, atomicity and live recovery NOT VERIFIED)")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--export-root", type=Path, required=True)
    p.add_argument("--private-evidence-dir", type=Path, required=True)
    p.add_argument("--volume-id", required=True)
    p.add_argument("--deployment-id", required=True)
    p.add_argument("--runtime-commit", required=True)
    p.add_argument("--rust-validator-bin", type=Path,
                   help="optional current-source Rust semantic validator; never authenticates provider identity")
    args = p.parse_args()
    try:
        run(args)
    except (ValueError, OSError, TypeError, UnicodeError) as e:
        # Do not print data, workspace identifiers, file names, paths or tokens.
        print("OFFHOST COPY STRUCTURAL REHEARSAL: BLOCKED (" +
              (str(e) if isinstance(e, ValueError) else type(e).__name__) + ")", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
