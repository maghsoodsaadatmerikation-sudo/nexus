#!/usr/bin/env python3
"""Standalone offline witness custodian: verify, retain, acknowledge and retrieve.

The custodian runs in an independent OS/trust domain (not deployed here).
No network listener, key provisioning, immutable backend or NEXUS import is
created by this CLI. The operator transports only small public receipts.
"""

import argparse
import base64
import binascii
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
    "nexus_external_witness", HERE / "workspace-offsite-witness.py"
)
if spec is None or spec.loader is None:
    raise RuntimeError("independent witness verifier unavailable")
witness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(witness)
trust = witness.trust

STORE_SCHEMA = "nexus.offsite.custodian-store.v1"
ACK_SCHEMA = "nexus.offsite.custodian-ack.v1"
PACKAGE_SCHEMA = "nexus.offsite.custodian-package.v1"
ACK_DOMAIN = b"NEXUS\x00offsite-custodian-receipt-ack\x00Ed25519\x00v1\x00"
STORE_FILE = "custodian.json"
MAX_STORE_BYTES = 2 * 1024 * 1024
MAX_ENTRIES = 256
MAX_PACKAGE_BYTES = 16 * 1024
ACK_BODY_FIELDS = {
    "schema", "algorithm", "receiver_id", "sequence", "source_key_id",
    "ack_key_id", "source_receipt_sha256", "state_sha256",
    "previous_ack_sha256",
}
ACK_FIELDS = ACK_BODY_FIELDS | {"signature_base64"}
PACKAGE_FIELDS = {"schema", "receipt", "ack"}


class CustodianError(Exception):
    pass


def fail(message):
    raise CustodianError(message)


def digest(obj):
    return hashlib.sha256(trust.encode_json(obj)).hexdigest()


def key_id(value):
    return trust.valid_key_id(value)


def parse_limited(path: Path, limit: int):
    return trust.strict_json(trust.open_no_symlinks(path, limit))


def public_from_der(der):
    trust.validate_public_der(der)
    return trust.public_key_pem(der)


def secure_inputs(source_public, ack_public, source_id, ack_id):
    key_id(source_id)
    key_id(ack_id)
    if source_id == ack_id:
        fail("source and custodian key IDs must be distinct")
    source_der = trust.derive_ed25519_public_der(source_public)
    ack_der = trust.derive_ed25519_public_der(ack_public)
    if source_der == ack_der:
        fail("source and custodian keys must be distinct")
    return source_der, ack_der


def empty_store(receiver_id, source_key_id, source_der, ack_key_id, ack_der):
    key_id(receiver_id)
    return {
        "schema": STORE_SCHEMA,
        "receiver_id": receiver_id,
        "source_key_id": source_key_id,
        "source_public_der_base64": base64.b64encode(source_der).decode("ascii"),
        "ack_key_id": ack_key_id,
        "ack_public_der_base64": base64.b64encode(ack_der).decode("ascii"),
        "entries": [],
    }


def derived_keys(data):
    try:
        source_der = base64.b64decode(data["source_public_der_base64"], validate=True)
        ack_der = base64.b64decode(data["ack_public_der_base64"], validate=True)
    except (ValueError, binascii.Error, TypeError) as exc:
        raise CustodianError("malformed pinned custodian public key") from exc
    trust.validate_public_der(source_der)
    trust.validate_public_der(ack_der)
    if source_der == ack_der:
        fail("custodian and source public keys must differ")
    return source_der, ack_der


def ack_preimage(body):
    data = trust.encode_json(body)
    return ACK_DOMAIN + len(data).to_bytes(8, "big") + data


def validated_ack(ack, receipt, receiver_id, source_id, ack_id, sequence, previous, pubpath):
    if not isinstance(ack, dict) or set(ack) != ACK_FIELDS:
        fail("unknown or malformed signed acknowledgment fields")
    if (ack["schema"] != ACK_SCHEMA or ack["algorithm"] != "Ed25519"
            or ack["receiver_id"] != receiver_id
            or type(ack["sequence"]) is not int or ack["sequence"] != sequence
            or ack["source_key_id"] != source_id or ack["ack_key_id"] != ack_id
            or ack["source_receipt_sha256"] != digest(receipt)
            or ack["state_sha256"] != receipt["state_sha256"]
            or ack["previous_ack_sha256"] != previous):
        fail("custodian signed acknowledgment does not bind received state and chain")
    try:
        sig = base64.b64decode(ack["signature_base64"], validate=True)
    except (binascii.Error, ValueError, TypeError) as exc:
        raise CustodianError("malformed custodian signature") from exc
    if len(sig) != 64:
        fail("invalid acknowledgment signature size")
    body = {field: ack[field] for field in ACK_BODY_FIELDS}
    try:
        trust.attestation.openssl("verify", pubpath, ack_preimage(body), sig)
    except trust.attestation.AttestationError as exc:
        raise CustodianError("custodian acknowledgment signature rejected") from exc


def validated_receipt(receipt, pubpath, source_id):
    if not isinstance(receipt, dict):
        fail("external receipt must be a JSON object")
    if set(receipt) != witness.SIGNED_FIELDS:
        fail("unrecognized external receipt fields")
    # Verify the exact existing v1 signer contract with the independently pinned key.
    witness.read_receipt  # The same explicit schema is checked below.
    if (receipt["schema"] != witness.SCHEMA
            or receipt["algorithm"] != witness.ALGORITHM
            or receipt["role"] != witness.ROLE
            or receipt["state_schema"] != trust.STATE_SCHEMA):
        fail("invalid external receipt role or schema")
    for field in ("state_sha256", "public_key_sha256"):
        if not isinstance(receipt[field], str) or not witness.HEX32.fullmatch(receipt[field]):
            fail("invalid receipt digest encoding")
    if (type(receipt["state_size_bytes"]) is not int
            or not 1 <= receipt["state_size_bytes"] <= trust.MAX_STATE_BYTES
            or type(receipt["key_count"]) is not int
            or not 0 <= receipt["key_count"] <= trust.MAX_KEYS
            or type(receipt["workspace_count"]) is not int
            or not 0 <= receipt["workspace_count"] <= trust.MAX_WORKSPACES
            or not isinstance(receipt["checkpoint_nonce_hex"], str)
            or not witness.HEX16.fullmatch(receipt["checkpoint_nonce_hex"])):
        fail("invalid receipt metadata constraints")
    if (receipt["witness_key_id"] != source_id
            or not isinstance(receipt["signature_base64"], str)):
        fail("source witness signer mismatch")
    try:
        sig = base64.b64decode(receipt["signature_base64"], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise CustodianError("invalid source receipt signature encoding") from exc
    if len(sig) != 64:
        fail("invalid source receipt signature length")
    try:
        witness.independent_verification(receipt, pubpath, source_id)
    except (witness.WitnessError, trust.TrustError) as exc:
        raise CustodianError("external witness signature is not independently trusted") from exc


def inspect_store(value):
    if (not isinstance(value, dict)
            or set(value) != {
                "schema", "receiver_id", "source_key_id", "source_public_der_base64",
                "ack_key_id", "ack_public_der_base64", "entries",
            }
            or value["schema"] != STORE_SCHEMA
            or not isinstance(value["entries"], list)
            or len(value["entries"]) > MAX_ENTRIES):
        fail("invalid or oversized custodian ledger")
    for name in ("receiver_id", "source_key_id", "ack_key_id"):
        key_id(value[name])
    if value["source_key_id"] == value["ack_key_id"]:
        fail("role key ID reuse is forbidden")
    source_der, ack_der = derived_keys(value)
    with tempfile.TemporaryDirectory(prefix="nexus-custodian-key-check-") as directory:
        root = Path(directory)
        source_pub = root / "source.pub.pem"
        ack_pub = root / "ack.pub.pem"
        source_pub.write_bytes(public_from_der(source_der))
        ack_pub.write_bytes(public_from_der(ack_der))
        previous = "0" * 64
        seen_receipts = set()
        seen_states = set()
        for index, entry in enumerate(value["entries"], start=1):
            if not isinstance(entry, dict) or set(entry) != {"receipt", "ack"}:
                fail("invalid custodian entry")
            receipt, ack = entry["receipt"], entry["ack"]
            validated_receipt(receipt, source_pub, value["source_key_id"])
            validated_ack(
                ack, receipt, value["receiver_id"], value["source_key_id"],
                value["ack_key_id"], index, previous, ack_pub,
            )
            receipt_sha = digest(receipt)
            state_sha = receipt["state_sha256"]
            if receipt_sha in seen_receipts or state_sha in seen_states:
                fail("replayed source receipt or previously accepted state")
            seen_receipts.add(receipt_sha)
            seen_states.add(state_sha)
            previous = digest(ack)
    return value


def read_store(directory_fd):
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(STORE_FILE, flags, dir_fd=directory_fd)
    except OSError as exc:
        raise CustodianError("custodian ledger is missing; init is explicit") from exc
    with os.fdopen(fd, "rb") as stream:
        m = os.fstat(stream.fileno())
        if (not stat.S_ISREG(m.st_mode) or m.st_nlink != 1
                or m.st_uid != os.geteuid() or m.st_mode & 0o077
                or m.st_size > MAX_STORE_BYTES):
            fail("unsafe custodian ledger ownership or permissions")
        raw = stream.read(MAX_STORE_BYTES + 1)
    if not raw or len(raw) > MAX_STORE_BYTES:
        fail("invalid custodian ledger file size")
    return inspect_store(trust.strict_json(raw))


def write_store(directory_fd, value):
    raw = trust.encode_json(inspect_store(value))
    if len(raw) > MAX_STORE_BYTES:
        fail("custodian ledger full")
    temporary = ".custodian-next-" + os.urandom(12).hex()
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(temporary, flags, 0o600, dir_fd=directory_fd)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, STORE_FILE, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        os.fsync(directory_fd)
    finally:
        try:
            os.unlink(temporary, dir_fd=directory_fd)
        except FileNotFoundError:
            pass


def init(args):
    source_der, ack_der = secure_inputs(
        args.source_public_key, args.ack_public_key,
        args.source_key_id, args.ack_key_id,
    )
    try:
        os.mkdir(args.store, 0o700)
    except OSError as exc:
        raise CustodianError("custodian directory already exists or is not writable") from exc
    fd = trust.protected_directory(args.store)
    try:
        write_store(fd, empty_store(
            args.receiver_id, args.source_key_id, source_der,
            args.ack_key_id, ack_der,
        ))
    finally:
        os.close(fd)
    print("CUSTODIAN INITIALIZED: public keys pinned, no remote service or import authority")


def receive(data, args):
    if len(data["entries"]) >= MAX_ENTRIES:
        fail("custodian capacity reached")
    receipt = parse_limited(args.receipt, witness.MAX_RECEIPT_BYTES)
    source_der, ack_der = derived_keys(data)
    with tempfile.TemporaryDirectory(prefix="nexus-custodian-accept-") as directory:
        root = Path(directory)
        source_pub = root / "source.pub.pem"
        source_pub.write_bytes(public_from_der(source_der))
        validated_receipt(receipt, source_pub, data["source_key_id"])
    if (any(entry["receipt"]["state_sha256"] == receipt["state_sha256"]
            or digest(entry["receipt"]) == digest(receipt)
            for entry in data["entries"])):
        fail("replay or previously accepted state")
    protected = args.store.resolve()
    if protected in args.ack_private_key.resolve().parents:
        fail("custodian private signing key must remain outside the ledger")
    signer_der = witness.private_signer(args.ack_private_key)
    if signer_der != ack_der or signer_der == source_der:
        fail("custodian private key does not match independently pinned receiver key")
    previous = digest(data["entries"][-1]["ack"]) if data["entries"] else "0" * 64
    body = {
        "schema": ACK_SCHEMA,
        "algorithm": "Ed25519",
        "receiver_id": data["receiver_id"],
        "sequence": len(data["entries"]) + 1,
        "source_key_id": data["source_key_id"],
        "ack_key_id": data["ack_key_id"],
        "source_receipt_sha256": digest(receipt),
        "state_sha256": receipt["state_sha256"],
        "previous_ack_sha256": previous,
    }
    try:
        sig = trust.attestation.openssl(
            "sign", args.ack_private_key, ack_preimage(body)
        )
    except trust.attestation.AttestationError as exc:
        raise CustodianError("custodian signing failed") from exc
    if len(sig) != 64:
        fail("invalid custodian signature output")
    ack = {**body, "signature_base64": base64.b64encode(sig).decode("ascii")}
    entry = {"receipt": receipt, "ack": ack}
    data["entries"].append(entry)
    return {"schema": PACKAGE_SCHEMA, **entry}


def latest(data):
    if not data["entries"]:
        fail("no acknowledged receipt; cannot claim a latest version")
    return {"schema": PACKAGE_SCHEMA, **data["entries"][-1]}


def independent_verify_package(package, args):
    if not isinstance(package, dict) or set(package) != PACKAGE_FIELDS:
        fail("malformed receipt-and-acknowledgment package")
    source_der, ack_der = secure_inputs(
        args.trusted_source_public_key,
        args.trusted_ack_public_key,
        args.trusted_source_key_id,
        args.trusted_ack_key_id,
    )
    if not isinstance(args.minimum_sequence, int) or args.minimum_sequence < 1:
        fail("invalid minimum sequence")
    receipt = package["receipt"]
    ack = package["ack"]
    with tempfile.TemporaryDirectory(prefix="nexus-independent-receipt-check-") as directory:
        root = Path(directory)
        source_pub = root / "source.pem"
        ack_pub = root / "ack.pem"
        source_pub.write_bytes(public_from_der(source_der))
        ack_pub.write_bytes(public_from_der(ack_der))
        validated_receipt(receipt, source_pub, args.trusted_source_key_id)
        if not isinstance(ack, dict) or type(ack.get("sequence")) is not int:
            fail("invalid acknowledgment sequence")
        if ack["sequence"] < args.minimum_sequence:
            fail("stale acknowledgment against client-pinned minimum sequence")
        previous = ack.get("previous_ack_sha256")
        if not isinstance(previous, str) or not witness.HEX32.fullmatch(previous):
            fail("invalid previous acknowledgment digest")
        validated_ack(
            ack, receipt, args.expected_receiver_id, args.trusted_source_key_id,
            args.trusted_ack_key_id, ack["sequence"], previous, ack_pub,
        )
    if args.state_dir is not None:
        # Reuse the strict, locked Rust-adjacent operator registry state reader.
        expected_state, _ = witness.state_bytes(args.state_dir)
        raw = trust.encode_json(expected_state)
        if (hashlib.sha256(raw).hexdigest() != receipt["state_sha256"]
                or len(raw) != receipt["state_size_bytes"]
                or len(expected_state["keys"]) != receipt["key_count"]
                or len(expected_state["workspaces"]) != receipt["workspace_count"]):
            fail("LOCAL TRUST ROLLBACK OR DIVERGENCE: current state differs from acknowledged checkpoint")
    print("INDEPENDENT RECEIPT PACKAGE VERIFIED: signer/sequence/state; freshness requires trusted receiver")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="action", required=True)
    setup = modes.add_parser("init")
    setup.add_argument("--store", type=Path, required=True)
    setup.add_argument("--receiver-id", required=True)
    setup.add_argument("--source-key-id", required=True)
    setup.add_argument("--source-public-key", type=Path, required=True)
    setup.add_argument("--ack-key-id", required=True)
    setup.add_argument("--ack-public-key", type=Path, required=True)
    receiver = modes.add_parser("receive")
    receiver.add_argument("--store", type=Path, required=True)
    receiver.add_argument("--receipt", type=Path, required=True)
    receiver.add_argument("--ack-private-key", type=Path, required=True)
    query = modes.add_parser("latest")
    query.add_argument("--store", type=Path, required=True)
    verifier = modes.add_parser("verify-package")
    verifier.add_argument("--package", type=Path, required=True)
    verifier.add_argument("--expected-receiver-id", required=True)
    verifier.add_argument("--trusted-source-key-id", required=True)
    verifier.add_argument("--trusted-source-public-key", type=Path, required=True)
    verifier.add_argument("--trusted-ack-key-id", required=True)
    verifier.add_argument("--trusted-ack-public-key", type=Path, required=True)
    verifier.add_argument("--minimum-sequence", type=int, default=1)
    verifier.add_argument("--state-dir", type=Path)

    args = parser.parse_args()
    try:
        if args.action == "init":
            init(args)
            return 0
        if args.action == "verify-package":
            independent_verify_package(parse_limited(args.package, 2 * witness.MAX_RECEIPT_BYTES), args)
            return 0
        fd = trust.protected_directory(args.store)
        try:
            data = read_store(fd)
            if args.action == "receive":
                package = receive(data, args)
                write_store(fd, data)
            else:
                package = latest(data)
        finally:
            os.close(fd)
        print(json.dumps(package, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    except (CustodianError, witness.WitnessError, trust.TrustError,
            OSError, ValueError, TypeError) as exc:
        print("INDEPENDENT CUSTODIAN DENIED: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
