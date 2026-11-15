#!/usr/bin/env python3
"""Offline export, verify, and fresh-directory restore of staged v2 witness history.

Requires independently pinned SHA-256 of the backup, bridge and latest signed
checkpoint, and a separately retained monotonic sequence floor. No private keys,
production service changes, runtime imports or witness independence claims.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "nexus_v2_recovery_stage", HERE / "workspace-witness-v2-stager.py")
if spec is None or spec.loader is None:
    raise RuntimeError("v2 candidate stager missing")
stager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stager)
v2 = stager.v2
trust = stager.trust

SCHEMA = "nexus.offsite.v2-candidate-backup.v1"
FIELDS = {"schema", "candidate", "candidate_sha256", "latest_ack_sha256",
          "latest_sequence"}
MAX_BACKUP_BYTES = stager.MAX + 16 * 1024


class RecoveryError(Exception):
    pass


def fail(message):
    raise RecoveryError(message)


def approved_sha(value, label):
    if not isinstance(value, str) or not v2.HEX.fullmatch(value):
        fail("independent " + label + " SHA-256 pin must be 64 lowercase hex")
    return value


def private_parent(path):
    # Do not accidentally create a backup in a shared/untrusted directory.
    if not path.is_absolute():
        fail("destination must be an explicit absolute path")
    parent = path.parent
    parent_stat = os.stat(parent, follow_symlinks=False)
    if (not stat.S_ISDIR(parent_stat.st_mode)
            or parent_stat.st_uid != os.geteuid()
            or parent_stat.st_mode & 0o077):
        fail("destination parent must be operator-owned and private")
    return parent


def independent_proof(args, candidate_bytes, candidate_sha):
    with tempfile.TemporaryDirectory(prefix="nexus-v2-recovery-proof-") as root:
        candidate_path = Path(root) / "candidate.json"
        candidate_path.write_bytes(candidate_bytes)
        return stager.verified_proof(
            args, candidate_path, candidate_sha,
            args.trusted_latest_package, args.trusted_latest_package_sha256,
            args.minimum_sequence)


def exact_pinned_backup(args):
    approved_sha(args.backup_sha256, "backup")
    approved_sha(args.expected_bridge_sha256, "bridge")
    raw_backup = trust.open_no_symlinks(args.backup, MAX_BACKUP_BYTES)
    if stager.digest(raw_backup) != args.backup_sha256:
        fail("cold backup differs from independently approved exact bytes")
    backup = trust.strict_json(raw_backup)
    if trust.encode_json(backup) != raw_backup:
        fail("cold backup requires unique canonical JSON bytes")
    if (not isinstance(backup, dict) or set(backup) != FIELDS
            or backup["schema"] != SCHEMA
            or type(backup["latest_sequence"]) is not int
            or backup["latest_sequence"] < 2):
        fail("malformed v2 backup envelope")
    approved_sha(backup["candidate_sha256"], "embedded candidate")
    approved_sha(backup["latest_ack_sha256"], "latest acknowledgment")
    if backup["candidate_sha256"] != args.expected_bridge_sha256:
        fail("cold backup head differs from independently approved bridge")
    bridge = backup["candidate"]
    if (not isinstance(bridge, dict) or set(bridge) != v2.BRIDGE_FIELDS
            or not isinstance(bridge["entries"], list)
            or not bridge["entries"]):
        fail("backup carries an unrecognized or empty v2 candidate")
    raw = trust.encode_json(bridge)
    if (len(raw) > stager.MAX or stager.digest(raw) != backup["candidate_sha256"]):
        fail("embedded candidate differs from independently pinned bytes")
    if stager.digest(trust.encode_json(bridge["entries"][-1]["ack"])) != backup["latest_ack_sha256"]:
        fail("backup latest acknowledgment digest differs from signed tail")
    return backup, raw


def verify_backup(args):
    obj, raw = exact_pinned_backup(args)
    proof = independent_proof(args, raw, args.expected_bridge_sha256)
    if (obj["latest_sequence"] != proof["new_sequence"]
            or obj["latest_ack_sha256"] != proof["new_last_ack_sha256"]):
        fail("backup differs from externally signed latest checkpoint")
    return obj, raw, proof


def backup_envelope(raw, proof):
    bridge = trust.strict_json(raw)
    obj = {
        "schema": SCHEMA,
        "candidate": bridge,
        "candidate_sha256": stager.digest(raw),
        "latest_ack_sha256": proof["new_last_ack_sha256"],
        "latest_sequence": proof["new_sequence"],
    }
    data = trust.encode_json(obj)
    if len(data) > MAX_BACKUP_BYTES:
        fail("backed-up candidate exceeds strict size cap")
    return data


def exclusive_backup(path, data):
    private_parent(path)
    flags = (os.O_WRONLY | os.O_CREAT | os.O_EXCL
             | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0))
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        parent_fd = os.open(
            path.parent, os.O_RDONLY | os.O_DIRECTORY
            | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0))
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except Exception:
        # Only the creation attempt's output may be removed; pre-existing
        # backups are never modified because O_EXCL rejects them.
        path.unlink(missing_ok=True)
        raise


def export(args):
    approved_sha(args.expected_bridge_sha256, "bridge")
    private_parent(args.backup)
    if not args.store.is_absolute():
        fail("staging store must be an absolute path")
    if args.store == args.backup.parent or args.store in args.backup.parents:
        fail("cold backup path must be outside staging directory")
    fd = trust.protected_directory(args.store)
    try:
        stager.assert_directory_identity(args.store, fd)
        raw = stager.read_locked(fd)
        if stager.digest(raw) != args.expected_bridge_sha256:
            fail("staging head differs from independently approved bridge")
        proof = independent_proof(args, raw, args.expected_bridge_sha256)
        data = backup_envelope(raw, proof)
        # No staging writes; backup is only a new private, exclusive file.
        stager.assert_directory_identity(args.store, fd)
        exclusive_backup(args.backup, data)
        stager.assert_directory_identity(args.store, fd)
    finally:
        os.close(fd)
    return {
        "schema": "nexus.offsite.v2-recovery-report.v1",
        "status": "exported-verifiable-cold-backup",
        "backup_sha256": stager.digest(data),
        "bridge_sha256": stager.digest(raw),
        "latest_sequence": proof["new_sequence"],
        "independent_remote_custody_proven": False,
        "production_import_authorized": False,
    }


def check(args):
    _, raw, proof = verify_backup(args)
    return {
        "schema": "nexus.offsite.v2-recovery-report.v1",
        "status": "cold-backup-cryptographically-verified",
        "backup_sha256": args.backup_sha256,
        "bridge_sha256": stager.digest(raw),
        "latest_sequence": proof["new_sequence"],
        "independent_remote_custody_proven": False,
        "production_import_authorized": False,
    }


def restore(args):
    private_parent(args.new_store)
    if not args.new_store.is_absolute():
        fail("new recovery store must be an absolute path")
    # The backup must never be relocated under the proposed fresh store.
    if (args.new_store == args.backup.parent
            or args.new_store in args.backup.parents
            or args.new_store in args.trusted_latest_package.parents):
        fail("recovery store overlaps an independent input location")
    if args.new_store.exists() or args.new_store.is_symlink():
        fail("refusing to overwrite an existing recovery directory")
    _, raw, proof = verify_backup(args)
    # Fresh directory ONLY after complete external signature checks.
    try:
        os.mkdir(args.new_store, 0o700)
    except OSError as exc:
        raise RecoveryError("fresh private restore directory is not available") from exc
    fd = trust.protected_directory(args.new_store)
    try:
        stager.assert_directory_identity(args.new_store, fd)
        stager.write_locked(fd, raw, expected=None)
        if stager.read_locked(fd) != raw:
            fail("round-trip durable recovery differs from pinned cold backup")
        stager.assert_directory_identity(args.new_store, fd)
    finally:
        os.close(fd)
    # Read the exact persisted bytes and verify the full chain again; only
    # the new offline staging area was written, not any v1/v2 live receiver.
    fd = trust.protected_directory(args.new_store)
    try:
        restored = stager.read_locked(fd)
        if stager.digest(restored) != args.expected_bridge_sha256:
            fail("recovery read-back SHA-256 differs from independently approved head")
        new_proof = independent_proof(
            args, restored, args.expected_bridge_sha256)
        if (new_proof["new_last_ack_sha256"] != proof["new_last_ack_sha256"]
                or new_proof["new_sequence"] != proof["new_sequence"]):
            fail("post-restore signed chain diverges from pre-restore proof")
        stager.assert_directory_identity(args.new_store, fd)
    finally:
        os.close(fd)
    return {
        "schema": "nexus.offsite.v2-recovery-report.v1",
        "status": "fresh-offline-stage-restored-and-reverified",
        "bridge_sha256": args.expected_bridge_sha256,
        "latest_sequence": proof["new_sequence"],
        "independent_remote_custody_proven": False,
        "production_import_authorized": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest="command", required=True)
    for name in ("export", "verify", "restore"):
        op = commands.add_parser(name)
        for flag in (
            "old-ledger", "trusted-old-package", "consent",
            "source-public-key", "outgoing-ack-public-key",
            "incoming-ack-public-key",
        ):
            op.add_argument("--" + flag, type=Path, required=True)
        for flag in (
            "old-ledger-sha256", "trusted-old-package-sha256",
            "consent-sha256", "receiver-id", "source-key-id",
            "outgoing-ack-key-id", "incoming-ack-key-id",
        ):
            op.add_argument("--" + flag, required=True)
        if name == "export":
            op.add_argument("--store", type=Path, required=True)
        op.add_argument("--expected-bridge-sha256", required=True)
        op.add_argument("--trusted-latest-package", type=Path, required=True)
        op.add_argument("--trusted-latest-package-sha256", required=True)
        op.add_argument("--minimum-sequence", type=int, required=True)
        op.add_argument("--backup", type=Path, required=True)
        if name in ("verify", "restore"):
            op.add_argument("--backup-sha256", required=True)
        if name == "restore":
            op.add_argument("--new-store", type=Path, required=True)
    args = p.parse_args()
    try:
        answer = {
            "export": export,
            "verify": check,
            "restore": restore,
        }[args.command](args)
        print(json.dumps(answer, separators=(",", ":"), sort_keys=True))
        return 0
    except (RecoveryError, stager.StageError, v2.EpochError,
            v2.transition.ConsentError, v2.custodian.CustodianError,
            v2.custodian.witness.WitnessError, trust.TrustError,
            OSError, ValueError, TypeError, KeyError) as exc:
        print("NEXUS V2 RECOVERY DENIED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
