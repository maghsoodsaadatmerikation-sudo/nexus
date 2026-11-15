#!/usr/bin/env python3
"""Offline, fail-closed NEXUS independent witness custodian backup/recovery.

Restores public receipt history only, never recipient private keys, and only
against a separately obtained latest signed acknowledgment and pinned key IDs.
No remote deployment, WORM guarantee or HTTP import authorization is granted.
"""

import argparse
import contextlib
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "nexus_recoverable_custodian", HERE / "workspace-witness-custodian.py"
)
if spec is None or spec.loader is None:
    raise RuntimeError("custodian verification unavailable")
custodian = importlib.util.module_from_spec(spec)
spec.loader.exec_module(custodian)
trust = custodian.trust

BACKUP_SCHEMA = "nexus.offsite.custodian-backup.v1"
MAX_BACKUP_BYTES = custodian.MAX_STORE_BYTES + 16 * 1024
BACKUP_FIELDS = {"schema", "store", "store_sha256", "latest_ack_sha256"}


class RecoveryError(Exception):
    pass


def fail(reason):
    raise RecoveryError(reason)


def digest_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def latest_package(store):
    if not store["entries"]:
        fail("cannot backup or restore an empty unacknowledged custodian")
    return {"schema": custodian.PACKAGE_SCHEMA, **store["entries"][-1]}


def trusted_checkpoint(path):
    return trust.strict_json(
        trust.open_no_symlinks(path, 2 * custodian.witness.MAX_RECEIPT_BYTES)
    )


def validate_independent_checkpoint(data, args):
    # The keys are selected by the recovery operator, NEVER by a backup or
    # untrusted receipt. The external package and minimum known sequence
    # must be retained in a different trust/failure domain.
    source_der, ack_der = custodian.secure_inputs(
        args.trusted_source_public_key, args.trusted_ack_public_key,
        args.trusted_source_key_id, args.trusted_ack_key_id
    )
    existing_source, existing_ack = custodian.derived_keys(data)
    if (existing_source != source_der or existing_ack != ack_der
            or data["source_key_id"] != args.trusted_source_key_id
            or data["ack_key_id"] != args.trusted_ack_key_id
            or data["receiver_id"] != args.expected_receiver_id):
        fail("stored receiver ID or signer public keys differ from independently pinned identity")
    if type(args.minimum_sequence) is not int or args.minimum_sequence < 1:
        fail("explicit independent minimum sequence required")
    package = trusted_checkpoint(args.trusted_checkpoint)
    auth = argparse.Namespace(
        expected_receiver_id=args.expected_receiver_id,
        trusted_source_key_id=args.trusted_source_key_id,
        trusted_source_public_key=args.trusted_source_public_key,
        trusted_ack_key_id=args.trusted_ack_key_id,
        trusted_ack_public_key=args.trusted_ack_public_key,
        minimum_sequence=args.minimum_sequence,
        state_dir=None,
    )
    with contextlib.redirect_stdout(io.StringIO()):
        custodian.independent_verify_package(package, auth)
    if package != latest_package(data):
        fail("backup latest acknowledgment differs from independently retained checkpoint")
    if package["ack"]["sequence"] != len(data["entries"]):
        fail("backup sequence disagrees with verified custodian ledger")
    return package


def parse_backup(path):
    obj = trust.strict_json(trust.open_no_symlinks(path, MAX_BACKUP_BYTES))
    if (not isinstance(obj, dict) or set(obj) != BACKUP_FIELDS
            or obj["schema"] != BACKUP_SCHEMA
            or not isinstance(obj["store_sha256"], str)
            or not trust.SHA256_HEX.fullmatch(obj["store_sha256"])
            or not isinstance(obj["latest_ack_sha256"], str)
            or not trust.SHA256_HEX.fullmatch(obj["latest_ack_sha256"])):
        fail("unsupported or malformed custodian backup envelope")
    store = custodian.inspect_store(obj["store"])
    raw = trust.encode_json(store)
    if len(raw) > custodian.MAX_STORE_BYTES or digest_bytes(raw) != obj["store_sha256"]:
        fail("custodian backup SHA-256 or size mismatch")
    if custodian.digest(store["entries"][-1]["ack"]) != obj["latest_ack_sha256"]:
        fail("custodian latest acknowledgment digest mismatch")
    return store


def pack(data):
    store_bytes = trust.encode_json(data)
    if len(store_bytes) > custodian.MAX_STORE_BYTES:
        fail("custodian export exceeds bounded state size")
    result = {
        "schema": BACKUP_SCHEMA,
        "store": data,
        "store_sha256": digest_bytes(store_bytes),
        "latest_ack_sha256": custodian.digest(data["entries"][-1]["ack"]),
    }
    raw = trust.encode_json(result)
    if len(raw) > MAX_BACKUP_BYTES:
        fail("backup envelope exceeds bounded capacity")
    return raw


def write_export(path, content):
    # Exclusive creation avoids silently changing the only externally
    # acknowledged backup; no overwrite, links or implicit directories.
    if not path.is_absolute():
        fail("export requires absolute operator-chosen destination")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as exc:
        raise RecoveryError("backup destination exists or is unsafe") from exc
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except Exception:
        path.unlink(missing_ok=True)
        raise


def export(args):
    if not args.store.is_absolute():
        fail("custodian store must use an absolute directory path")
    if args.store.resolve() in args.backup.resolve().parents:
        fail("recovery backup must reside outside the custodian store")
    if args.store.resolve() in args.trusted_checkpoint.resolve().parents:
        fail("latest trust checkpoint cannot be held within the custodian store")
    fd = trust.protected_directory(args.store)
    try:
        data = custodian.read_store(fd)
        validate_independent_checkpoint(data, args)
        write_export(args.backup, pack(data))
    finally:
        os.close(fd)
    print("CUSTODIAN BACKUP EXPORTED: complete signed public history; no private key")


def restore(args):
    if not args.new_store.is_absolute():
        fail("recovery destination must be an explicit absolute directory")
    if (args.new_store.exists() or args.new_store.is_symlink()
            or args.new_store.resolve() in args.backup.resolve().parents
            or args.new_store.resolve() in args.trusted_checkpoint.resolve().parents):
        fail("restore destination already exists or contains external recovery material")
    data = parse_backup(args.backup)
    validate_independent_checkpoint(data, args)
    # No partial old ledger is overwritten or merged. The new private
    # directory is created only after full independent cryptographic checks.
    try:
        os.mkdir(args.new_store, 0o700)
    except OSError as exc:
        raise RecoveryError("recovery directory is not vacant or cannot be created") from exc
    fd = trust.protected_directory(args.new_store)
    try:
        custodian.write_store(fd, data)
    finally:
        os.close(fd)
    # A successful recovery is not sufficient for operational service until
    # signer private keys are restored *separately* and a new receipt is signed.
    print("CUSTODIAN RESTORED: signed chain verified; private keys NOT restored; authority=none")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    for name in ("export", "restore"):
        cmd = actions.add_parser(name)
        if name == "export":
            cmd.add_argument("--store", type=Path, required=True)
        else:
            cmd.add_argument("--new-store", type=Path, required=True)
        cmd.add_argument("--backup", type=Path, required=True)
        cmd.add_argument("--trusted-checkpoint", type=Path, required=True)
        cmd.add_argument("--expected-receiver-id", required=True)
        cmd.add_argument("--trusted-source-key-id", required=True)
        cmd.add_argument("--trusted-source-public-key", type=Path, required=True)
        cmd.add_argument("--trusted-ack-key-id", required=True)
        cmd.add_argument("--trusted-ack-public-key", type=Path, required=True)
        cmd.add_argument("--minimum-sequence", type=int, required=True)
    args = parser.parse_args()
    try:
        if args.action == "export":
            export(args)
        else:
            restore(args)
    except (RecoveryError, custodian.CustodianError, custodian.witness.WitnessError,
            trust.TrustError, OSError, ValueError, TypeError) as exc:
        print("CUSTODIAN RECOVERY DENIED: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
