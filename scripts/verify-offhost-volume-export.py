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
import sys

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
    snapshot.backup(source, archive)
    inspection = snapshot.inspect_snapshot(archive)
    restored = output / "isolated-restore-rehearsal"
    snapshot.restore(archive, restored)
    expected = dict(snapshot.validated_records(archive))
    expected.pop(snapshot.RECOVERY_MARKER, None)
    actual_names = {p.relative_to(restored).as_posix()
                    for p in restored.rglob("*") if not p.is_dir()}
    require(actual_names == set(expected) | {snapshot.RECOVERY_MARKER},
            "isolated restored file set differs from archived data")
    for name, data in expected.items():
        require(snapshot.read_regular(restored / name, snapshot.MAX_BYTES) == data,
                "isolated restored data differs from archive")
    require(snapshot.read_regular(restored / snapshot.RECOVERY_MARKER,
                                  len(snapshot.RECOVERY_BYTES)) == snapshot.RECOVERY_BYTES,
            "restore quarantine is missing")
    archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
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
    print("OFFHOST COPY STRUCTURAL REHEARSAL: PASS (origin and live recovery NOT VERIFIED)")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--export-root", type=Path, required=True)
    p.add_argument("--private-evidence-dir", type=Path, required=True)
    p.add_argument("--volume-id", required=True)
    p.add_argument("--deployment-id", required=True)
    p.add_argument("--runtime-commit", required=True)
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
