#!/usr/bin/env python3
"""Offline, bounded snapshots of the complete supported NEXUS data layout.

Backup, restore and resume require all writers to stay stopped until completion.
Inspect/compare read existing archives and do not assert live-volume consistency.
Checksums detect corruption; they do not authenticate the snapshot or grant authority.
"""
import argparse
import base64
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile

SCHEMA = "nexus.data-snapshot.v1"
MAX_BYTES = 64 * 1024 * 1024
MAX_FILES = 20_000
RECOVERY_MARKER = ".nexus-recovery-required"
RECOVERY_BYTES = b"snapshot-restored; replay-risk-not-acknowledged\n"


class SnapshotError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise SnapshotError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def validate_file(name, data):
    require(isinstance(name, str), "invalid path")
    if name == RECOVERY_MARKER:
        require(data == RECOVERY_BYTES, "invalid recovery quarantine marker")
    elif re.fullmatch(r"requests/[0-9a-f]{2,200}", name):
        encoded = name.split("/")[1]
        require(len(encoded) % 2 == 0, "invalid request ID encoding")
        bytes.fromhex(encoded).decode("utf-8")
        require(b"pending\n".startswith(data), "invalid request marker")
    else:
        require(re.fullmatch(r"(?:[0-9a-f]{2})*\.json", name), "unsupported data path")
        workspace_id = bytes.fromhex(name[:-5]).decode("utf-8")
        snapshot = json.loads(data, object_pairs_hook=unique_object)
        require(isinstance(snapshot, dict) and type(snapshot.get("schema_version")) is int and snapshot["schema_version"] == 1,
                "unsupported workspace schema")
        require(isinstance(snapshot.get("workspace"), dict) and
                snapshot["workspace"].get("id") == workspace_id, "workspace ID mismatch")
        # The constitutional core still revalidates audit history when loaded.


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def read_regular(path, limit):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode), "only regular files are supported")
        require(before.st_size <= limit, "snapshot size limit exceeded")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            data = handle.read(limit + 1)
        after = os.fstat(fd)
        require(len(data) <= limit, "snapshot size limit exceeded")
        require((before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                "data changed during snapshot")
        return data
    finally:
        os.close(fd)


def backup(source, output):
    require(not source.is_symlink() and source.is_dir(), "source must be a real directory")
    source = source.resolve()
    output = output.absolute()
    require(not output.resolve().is_relative_to(source), "backup must be outside the data directory")
    require(output.parent.is_dir(), "backup parent directory must exist")
    require(not output.exists() and not output.is_symlink(), "backup output already exists")
    request_dir = source / "requests"
    require(request_dir.is_dir() and not request_dir.is_symlink(), "request ledger is required")
    candidates = []
    for entry in source.iterdir():
        if entry.name == "requests":
            candidates.extend(entry.iterdir())
        else:
            candidates.append(entry)
    require(len(candidates) <= MAX_FILES, "snapshot file limit exceeded")
    records = []
    total = 0
    for path in sorted(candidates):
        data = read_regular(path, MAX_BYTES - total)
        total += len(data)
        name = path.relative_to(source).as_posix()
        validate_file(name, data)
        records.append({"path": name, "size": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "data": base64.b64encode(data).decode("ascii")})
    document = {"schema": SCHEMA, "authority": "none",
                "consistency": "offline-caller-asserted", "files": records}
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    require(len(encoded) <= MAX_BYTES, "snapshot size limit exceeded")
    fd, temporary = tempfile.mkstemp(prefix=".nexus-snapshot-", dir=output.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        # Atomic publication without overwriting an existing artifact.
        os.link(temporary, output, follow_symlinks=False)
        sync_directory(output.parent)
    finally:
        os.unlink(temporary)
    return len(records)


def validated_records(archive):
    raw = read_regular(archive, MAX_BYTES)
    document = json.loads(raw, object_pairs_hook=unique_object)
    require(isinstance(document, dict) and set(document) ==
            {"schema", "authority", "consistency", "files"}, "invalid snapshot envelope")
    require(document["schema"] == SCHEMA and document["authority"] == "none" and
            document["consistency"] == "offline-caller-asserted", "unsupported snapshot contract")
    records = document["files"]
    require(isinstance(records, list) and len(records) <= MAX_FILES, "snapshot file limit exceeded")
    decoded = []
    seen = set()
    total = 0
    for record in records:
        require(isinstance(record, dict) and set(record) == {"path", "size", "sha256", "data"},
                "invalid file record")
        name = record["path"]
        require(isinstance(name, str) and name not in seen, "duplicate or invalid path")
        seen.add(name)
        require(isinstance(record["data"], str), "invalid encoded data")
        data = base64.b64decode(record["data"], validate=True)
        total += len(data)
        require(total <= MAX_BYTES, "snapshot size limit exceeded")
        require(type(record["size"]) is int and record["size"] == len(data), "size mismatch")
        require(record["sha256"] == hashlib.sha256(data).hexdigest(), "checksum mismatch")
        validate_file(name, data)
        decoded.append((name, data))
    return decoded


def inspect_snapshot(archive):
    """Report aggregate structure only; never disclose IDs or workspace content."""
    records = validated_records(archive)
    requests = [data for name, data in records if name.startswith("requests/")]
    pending = sum(data == b"pending\n" for data in requests)
    return {
        "schema": "nexus.snapshot-inspection.v1",
        "status": "STRUCTURALLY_VALID",
        "scope": "snapshot_structure_only",
        "file_count": len(records),
        "decoded_bytes": sum(len(data) for _, data in records),
        "workspace_count": sum(name.endswith(".json") for name, _ in records),
        "requests": {"pending": pending, "indeterminate": len(requests) - pending},
        "captured_quarantine": any(name == RECOVERY_MARKER for name, _ in records),
        "recovery_point": "unknown",
        "core_audit": "not_checked",
        "authenticity": "not_verified",
        "authority": "none",
    }


def compare_snapshots(reference_archive, candidate_archive):
    """Compare a proposed restore candidate with a reference, without ordering them."""
    reference = dict(validated_records(reference_archive))
    candidate = dict(validated_records(candidate_archive))
    reference_requests = {name for name in reference if name.startswith("requests/")}
    candidate_requests = {name for name in candidate if name.startswith("requests/")}
    shared_requests = reference_requests & candidate_requests
    reference_workspaces = {name for name in reference if name.endswith(".json")}
    candidate_workspaces = {name for name in candidate if name.endswith(".json")}
    shared_workspaces = reference_workspaces & candidate_workspaces
    return {
        "schema": "nexus.snapshot-comparison.v1",
        "status": "STRUCTURALLY_VALID_COMPARISON",
        "scope": "two_snapshot_structure_only",
        "requests": {
            "reference_count": len(reference_requests),
            "candidate_count": len(candidate_requests),
            "reference_ids_missing_from_candidate": len(reference_requests - candidate_requests),
            "candidate_ids_missing_from_reference": len(candidate_requests - reference_requests),
            "shared_count": len(shared_requests),
            "shared_marker_bytes_changed": sum(reference[name] != candidate[name]
                                               for name in shared_requests),
            "shared_pending_to_indeterminate": sum(reference[name] == b"pending\n" and
                candidate[name] != b"pending\n" for name in shared_requests),
            "shared_indeterminate_to_pending": sum(reference[name] != b"pending\n" and
                candidate[name] == b"pending\n" for name in shared_requests),
        },
        "workspaces": {
            "reference_count": len(reference_workspaces),
            "candidate_count": len(candidate_workspaces),
            "reference_ids_missing_from_candidate": len(reference_workspaces - candidate_workspaces),
            "candidate_ids_missing_from_reference": len(candidate_workspaces - reference_workspaces),
            "shared_bytes_changed": sum(reference[name] != candidate[name]
                                         for name in shared_workspaces),
        },
        "captured_quarantine": {"reference": RECOVERY_MARKER in reference,
                                "candidate": RECOVERY_MARKER in candidate},
        "chronology": "not_inferred",
        "recovery_point": "unknown",
        "core_audit": "not_checked",
        "authenticity": "not_verified",
        "authority": "none",
    }


def publish_directory_no_replace(stage, target):
    """Publish atomically on supported Linux filesystems; never fall back to rename."""
    require(sys.platform == "linux", "atomic no-replace restore requires Linux")
    try:
        renameat2 = ctypes.CDLL(None, use_errno=True).renameat2
    except (AttributeError, OSError):
        raise SnapshotError("atomic no-replace restore is unavailable") from None
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                          ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    # AT_FDCWD=-100; RENAME_NOREPLACE=1. The kernel checks target absence and
    # publishes in one operation, including when an empty directory races us.
    if renameat2(-100, os.fsencode(stage), -100, os.fsencode(target), 1) != 0:
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise SnapshotError("restore target appeared during restore")
        if error in (errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP):
            raise SnapshotError("atomic no-replace restore is unsupported")
        raise OSError(error, os.strerror(error))


def restore(archive, target, owner=None):
    # Validate every record before creating any destination state.
    records = validated_records(archive)
    target = target.absolute()
    require(target.parent.is_dir(), "restore parent directory must exist")
    require(not target.exists() and not target.is_symlink(), "restore target must not exist")
    stage = Path(tempfile.mkdtemp(prefix=".nexus-restore-", dir=target.parent))
    try:
        (stage / "requests").mkdir(mode=0o700)
        # Every restore is quarantined, even if the captured volume was resumed.
        records = [(name, data) for name, data in records if name != RECOVERY_MARKER]
        records.append((RECOVERY_MARKER, RECOVERY_BYTES))
        for name, data in records:
            path = stage / name
            with path.open("xb") as handle:
                os.chmod(path, 0o600)
                if owner is not None:
                    os.chown(path, *owner)
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        if owner is not None:
            os.chown(stage / "requests", *owner)
            os.chown(stage, *owner)
        sync_directory(stage / "requests")
        sync_directory(stage)
        require(not target.exists() and not target.is_symlink(), "restore target appeared during restore")
        # Offline exclusive maintenance and a trusted parent remain required.
        publish_directory_no_replace(stage, target)
        sync_directory(target.parent)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return len(records)


def resume(data_root):
    require(not data_root.is_symlink() and data_root.is_dir(), "data must be a real directory")
    data_root = data_root.resolve()
    marker = data_root / RECOVERY_MARKER
    validate_file(RECOVERY_MARKER, read_regular(marker, len(RECOVERY_BYTES)))
    marker.unlink()
    sync_directory(data_root)


def parse_owner(value):
    require(re.fullmatch(r"[0-9]+:[0-9]+", value), "owner must be numeric UID:GID")
    return tuple(map(int, value.split(":")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["backup", "restore", "resume", "inspect", "compare"])
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path, nargs="?",
                        help="backup/restore destination, or candidate archive for compare")
    parser.add_argument("--offline", action="store_true", help="assert all data writers are stopped")
    parser.add_argument("--owner", help="restore ownership as numeric UID:GID; requires appropriate privilege")
    parser.add_argument("--acknowledge-replay-risk", action="store_true",
                        help="explicitly accept loss of replay protection for post-snapshot IDs")
    args = parser.parse_args()
    try:
        if args.operation in ("inspect", "compare"):
            require(args.owner is None, "owner applies only to restore")
            require(not args.offline, "offline applies only to backup, restore or resume")
            require(not args.acknowledge_replay_risk,
                    "replay-risk acknowledgment applies only to resume")
            if args.operation == "inspect":
                require(args.destination is None, "inspect takes only the archive")
                report = inspect_snapshot(args.source)
            else:
                require(args.destination is not None, "compare requires reference and candidate archives")
                report = compare_snapshots(args.source, args.destination)
            print(json.dumps(report, sort_keys=True))
            return 0
        require(args.offline, "stop all writers and explicitly pass --offline")
        require(args.operation == "restore" or args.owner is None, "owner applies only to restore")
        if args.operation == "resume":
            require(args.destination is None, "resume takes only the data directory")
            require(args.acknowledge_replay_risk, "explicitly pass --acknowledge-replay-risk")
            resume(args.source)
            print("NEXUS DATA SNAPSHOT RESUME: PASS (replay-risk acknowledged; authority=none)")
            return 0
        require(args.destination is not None, "snapshot destination is required")
        require(not args.acknowledge_replay_risk, "replay-risk acknowledgment applies only to resume")
        if args.operation == "backup":
            count = backup(args.source, args.destination)
        else:
            count = restore(args.source, args.destination, parse_owner(args.owner) if args.owner else None)
        print(f"NEXUS DATA SNAPSHOT {args.operation.upper()}: PASS ({count} files; authority=none)")
    except (ValueError, OSError, UnicodeError, TypeError) as error:
        # Do not echo archive content, environment variables or private paths.
        reason = str(error) if isinstance(error, SnapshotError) else type(error).__name__
        print(f"NEXUS DATA SNAPSHOT: BLOCKED ({reason})", file=__import__("sys").stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
