#!/usr/bin/env python3
"""Offline durable STAGING of externally signed NEXUS v2 witness candidates.

No receipt signing, key cutover, production service changes or remote network.
The only write is a verified, canonical bridge JSON in a new private directory.
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
    "nexus_v2_stage_verifier", HERE / "workspace-witness-key-epoch-v2.py")
if spec is None or spec.loader is None:
    raise RuntimeError("NEXUS v2 verifier unavailable")
v2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v2)
trust = v2.trust
FILE = "candidate.json"
MAX = v2.MAX_BRIDGE_BYTES


class StageError(Exception):
    pass


def fail(message):
    raise StageError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def verified_candidate(path, approved_sha):
    data = v2.pinned(path, approved_sha, "staged candidate", MAX)
    raw = trust.encode_json(data)
    if digest(raw) != approved_sha:
        fail("candidate must use strict canonical JSON bytes; no implicit rewriting")
    return data, raw


def read_locked(directory_fd):
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        handle = os.open(FILE, flags, dir_fd=directory_fd)
    except OSError as exc:
        raise StageError("candidate absent, unsafe or inaccessible; no implicit rebootstrap") from exc
    with os.fdopen(handle, "rb") as stream:
        meta = os.fstat(stream.fileno())
        if (not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1
                or meta.st_uid != os.geteuid() or meta.st_mode & 0o077
                or meta.st_size > MAX):
            fail("candidate must be an operator-owned private regular file")
        raw = stream.read(MAX + 1)
    if not raw or len(raw) > MAX:
        fail("candidate absent or exceeds strict capacity")
    if trust.encode_json(trust.strict_json(raw)) != raw:
        fail("persisted candidate damaged or noncanonical")
    return raw


def write_locked(directory_fd, raw, expected):
    if not raw or len(raw) > MAX:
        fail("candidate exceeds strict capacity")
    # Verify the exact predecessor under lock immediately before the commit.
    if expected is None:
        try:
            os.stat(FILE, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            fail("staging candidate already exists; refusing overwrite")
    elif digest(read_locked(directory_fd)) != expected:
        fail("staging predecessor changed before durable commit")
    name = ".candidate-next-" + os.urandom(12).hex()
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(name, flags, 0o600, dir_fd=directory_fd)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, FILE, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        os.fsync(directory_fd)
    finally:
        try:
            os.unlink(name, dir_fd=directory_fd)
        except FileNotFoundError:
            pass


def verified_proof(args, candidate_path, candidate_sha, package_path,
                   package_sha, minimum):
    proof = argparse.Namespace(
        old_ledger=args.old_ledger,
        old_ledger_sha256=args.old_ledger_sha256,
        trusted_old_package=args.trusted_old_package,
        trusted_old_package_sha256=args.trusted_old_package_sha256,
        consent=args.consent,
        consent_sha256=args.consent_sha256,
        bridge=candidate_path,
        bridge_sha256=candidate_sha,
        trusted_new_package=package_path,
        trusted_new_package_sha256=package_sha,
        receiver_id=args.receiver_id,
        source_key_id=args.source_key_id,
        source_public_key=args.source_public_key,
        outgoing_ack_key_id=args.outgoing_ack_key_id,
        outgoing_ack_public_key=args.outgoing_ack_public_key,
        incoming_ack_key_id=args.incoming_ack_key_id,
        incoming_ack_public_key=args.incoming_ack_public_key,
        minimum_sequence=minimum,
    )
    return v2.verify(proof)


def commit_report(status, raw, proof):
    return {
        "schema": "nexus.offsite.v2-durable-candidate.v1",
        "status": status,
        "candidate_sha256": digest(raw),
        "latest_sequence": proof["new_sequence"],
        "durable_stage_only": True,
        "production_key_rotation_authorized": False,
    }


def initial(args):
    data, raw = verified_candidate(args.candidate, args.candidate_sha256)
    proof = verified_proof(
        args, args.candidate, args.candidate_sha256,
        args.trusted_next_package, args.trusted_next_package_sha256,
        args.next_minimum_sequence)
    # Refuse to use a populated directory as a fresh staging store.
    try:
        os.mkdir(args.store, 0o700)
    except OSError as exc:
        raise StageError("new staging directory must not already exist") from exc
    fd = trust.protected_directory(args.store)
    try:
        write_locked(fd, raw, expected=None)
    finally:
        os.close(fd)
    return commit_report("initialized-verified-v2-candidate", raw, proof)


def advance(args):
    new_data, new_bytes = verified_candidate(
        args.candidate, args.candidate_sha256)
    if (type(args.current_minimum_sequence) is not int
            or type(args.next_minimum_sequence) is not int
            or args.current_minimum_sequence < 1
            or args.next_minimum_sequence < args.current_minimum_sequence):
        fail("independent sequence floors cannot decrease")
    fd = trust.protected_directory(args.store)  # flock across cooperating processes
    try:
        stored_bytes = read_locked(fd)
        actual = digest(stored_bytes)
        if not isinstance(args.expected_current_sha256, str) or not v2.HEX.fullmatch(
                args.expected_current_sha256):
            fail("independently approved predecessor SHA-256 is required")
        with tempfile.TemporaryDirectory(prefix="nexus-v2-stage-proof-") as td:
            predecessor = Path(td) / "previous.json"
            if actual == args.expected_current_sha256:
                predecessor.write_bytes(stored_bytes)
                old_data = trust.strict_json(stored_bytes)
                if (len(new_data["entries"]) != len(old_data["entries"]) + 1
                        or {**new_data, "entries": old_data["entries"]} != old_data):
                    fail("new candidate must add exactly one entry to the signed predecessor")
                verified_proof(
                    args, predecessor, actual,
                    args.trusted_current_package, args.trusted_current_package_sha256,
                    args.current_minimum_sequence)
                next_proof = verified_proof(
                    args, args.candidate, args.candidate_sha256,
                    args.trusted_next_package, args.trusted_next_package_sha256,
                    args.next_minimum_sequence)
                write_locked(fd, new_bytes, expected=actual)
                return commit_report("appended-one-verified-v2-record", new_bytes, next_proof)
            if actual == args.candidate_sha256:
                # Lost client response AFTER fsync: accept only the exact
                # same single-entry candidate with the pinned predecessor.
                old_data = dict(new_data)
                if not isinstance(old_data.get("entries"), list) or len(
                        old_data["entries"]) <= 1:
                    fail("retry cannot reconstruct the pinned predecessor")
                old_data["entries"] = old_data["entries"][:-1]
                prefix_bytes = trust.encode_json(old_data)
                if digest(prefix_bytes) != args.expected_current_sha256:
                    fail("candidate already stored but requested predecessor differs")
                predecessor.write_bytes(prefix_bytes)
                verified_proof(
                    args, predecessor, digest(prefix_bytes),
                    args.trusted_current_package, args.trusted_current_package_sha256,
                    args.current_minimum_sequence)
                next_proof = verified_proof(
                    args, args.candidate, args.candidate_sha256,
                    args.trusted_next_package, args.trusted_next_package_sha256,
                    args.next_minimum_sequence)
                return commit_report("already-committed-exact-retry", stored_bytes, next_proof)
            fail("conflict: pinned predecessor differs from durable candidate")
    finally:
        os.close(fd)


def add_common(parser):
    for name in (
        "old-ledger", "trusted-old-package", "consent",
        "source-public-key", "outgoing-ack-public-key",
        "incoming-ack-public-key",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in (
        "old-ledger-sha256", "trusted-old-package-sha256", "consent-sha256",
        "receiver-id", "source-key-id",
        "outgoing-ack-key-id", "incoming-ack-key-id",
    ):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--candidate-sha256", required=True)
    parser.add_argument("--trusted-next-package", type=Path, required=True)
    parser.add_argument("--trusted-next-package-sha256", required=True)
    parser.add_argument("--next-minimum-sequence", type=int, required=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="create new staging directory from verified signed candidate")
    append = sub.add_parser("append", help="atomically stage exactly one further signed entry")
    for operation in (init, append):
        add_common(operation)
    append.add_argument("--expected-current-sha256", required=True)
    append.add_argument("--trusted-current-package", type=Path, required=True)
    append.add_argument("--trusted-current-package-sha256", required=True)
    append.add_argument("--current-minimum-sequence", type=int, required=True)
    args = parser.parse_args()
    try:
        answer = initial(args) if args.command == "init" else advance(args)
        print(json.dumps(answer, sort_keys=True, separators=(",", ":")))
        return 0
    except (StageError, v2.EpochError, v2.transition.ConsentError,
            v2.custodian.CustodianError, v2.custodian.witness.WitnessError,
            trust.TrustError, OSError, ValueError, TypeError, KeyError) as exc:
        print("NEXUS V2 DURABLE STAGING DENIED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
