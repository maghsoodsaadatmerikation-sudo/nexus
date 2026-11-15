#!/usr/bin/env python3
"""Independent Ed25519-signed checkpoint for the exact NEXUS trust-registry state.

A receipt must be copied to an independently controlled off-host/WORM location.
This script neither publishes it nor makes any storage medium immutable.
The public key must be independently pinned; the runtime import API is unchanged.
"""

import argparse
import base64
import binascii
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("nexus_offline_trust", ROOT / "workspace-trust.py")
if spec is None or spec.loader is None:
    raise RuntimeError("offline trust module unavailable")
trust = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trust)

SCHEMA = "nexus.workspace.offsite-state-witness.v1"
ALGORITHM = "Ed25519"
ROLE = "external_state_witness"
DOMAIN = b"NEXUS\x00offsite-trust-state\x00Ed25519\x00v1\x00"
MAX_RECEIPT_BYTES = 8192
FIELDS = {
    "schema", "algorithm", "role", "witness_key_id", "public_key_sha256",
    "state_schema", "state_size_bytes", "state_sha256",
    "key_count", "workspace_count", "checkpoint_nonce_hex",
}
SIGNED_FIELDS = FIELDS | {"signature_base64"}
HEX32 = re.compile(r"[0-9a-f]{64}\Z")
HEX16 = re.compile(r"[0-9a-f]{32}\Z")


class WitnessError(Exception):
    pass


def reject(reason):
    raise WitnessError(reason)


def private_signer(path: Path) -> bytes:
    # A signer needs a key held independently of the compromised trust store.
    try:
        meta = path.lstat()
    except OSError as exc:
        raise WitnessError("external witness private key missing") from exc
    if (not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1
            or meta.st_uid != os.geteuid() or meta.st_mode & 0o077):
        reject("external witness signing key must be operator-owned private regular file")
    try:
        public = subprocess.run(
            ["openssl", "pkey", "-in", str(path), "-pubout", "-outform", "DER"],
            capture_output=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WitnessError("external witness signing key unavailable") from exc
    if public.returncode != 0:
        reject("invalid external witness signing key")
    return trust.validate_public_der(public.stdout)


def state_bytes(directory: Path):
    # Protect against state replacement during the read; do not mutate it.
    fd = trust.protected_directory(directory)
    try:
        state = trust.read_state(fd)
        return state, trust.encode_json(state)
    finally:
        os.close(fd)


def payload(record: dict) -> bytes:
    return trust.encode_json(record)


def preimage(record: dict) -> bytes:
    raw = payload(record)
    return DOMAIN + len(raw).to_bytes(8, "big") + raw


def current_statement(directory: Path, witness_key_id: str, witness_der: bytes):
    state, raw = state_bytes(directory)
    return {
        "schema": SCHEMA,
        "algorithm": ALGORITHM,
        "role": ROLE,
        "witness_key_id": witness_key_id,
        "public_key_sha256": trust.fingerprint(witness_der),
        "state_schema": trust.STATE_SCHEMA,
        "state_size_bytes": len(raw),
        "state_sha256": hashlib.sha256(raw).hexdigest(),
        "key_count": len(state["keys"]),
        "workspace_count": len(state["workspaces"]),
    }, state


def read_receipt(path: Path) -> dict:
    data = trust.open_no_symlinks(path, MAX_RECEIPT_BYTES)
    document = trust.strict_json(data)
    if not isinstance(document, dict) or set(document) != SIGNED_FIELDS:
        reject("invalid or unsupported external witness envelope")
    if (document["schema"] != SCHEMA
            or document["algorithm"] != ALGORITHM
            or document["role"] != ROLE
            or document["state_schema"] != trust.STATE_SCHEMA
            or not isinstance(document["witness_key_id"], str)
            or not trust.KEY_ID.fullmatch(document["witness_key_id"])
            or not isinstance(document["public_key_sha256"], str)
            or not HEX32.fullmatch(document["public_key_sha256"])
            or not isinstance(document["state_sha256"], str)
            or not HEX32.fullmatch(document["state_sha256"])
            or not isinstance(document["checkpoint_nonce_hex"], str)
            or not HEX16.fullmatch(document["checkpoint_nonce_hex"])
            or type(document["state_size_bytes"]) is not int
            or not 1 <= document["state_size_bytes"] <= trust.MAX_STATE_BYTES
            or type(document["key_count"]) is not int
            or not 0 <= document["key_count"] <= trust.MAX_KEYS
            or type(document["workspace_count"]) is not int
            or not 0 <= document["workspace_count"] <= trust.MAX_WORKSPACES
            or not isinstance(document["signature_base64"], str)):
        reject("invalid external witness metadata")
    try:
        signature = base64.b64decode(document["signature_base64"], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise WitnessError("malformed external signature") from exc
    if len(signature) != 64:
        reject("invalid external Ed25519 signature length")
    return document


def independent_verification(receipt: dict, public_key_path: Path, key_id: str):
    trust.valid_key_id(key_id)
    if receipt["witness_key_id"] != key_id:
        reject("external signer identity not independently pinned")
    der = trust.derive_ed25519_public_der(public_key_path)
    if trust.fingerprint(der) != receipt["public_key_sha256"]:
        reject("external witness public key fingerprint mismatch")
    body = {key: receipt[key] for key in FIELDS}
    try:
        signature = base64.b64decode(receipt["signature_base64"], validate=True)
        trust.attestation.openssl(
            "verify", public_key_path, preimage(body), signature,
        )
    except trust.attestation.AttestationError as exc:
        raise WitnessError("independent Ed25519 signature verification failed") from exc
    return body


def write_exclusive(path: Path, document: dict):
    raw = trust.encode_json(document)
    if len(raw) > MAX_RECEIPT_BYTES:
        reject("external receipt capacity exceeded")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as exc:
        raise WitnessError("receipt path already exists or is unsafe") from exc
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise
    # fsync parent to make freshly created receipt durable before external copy.
    parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


def seal(args):
    protected = args.state_dir.resolve()
    if args.output.resolve() == protected / trust.STATE_FILE:
        reject("witness cannot replace trust-state")
    if protected in args.output.resolve().parents:
        reject("witness receipt must be outside the trust directory")
    if protected in args.witness_private_key.resolve().parents:
        reject("independent witness signer cannot reside in the trust directory")
    if args.witness_private_key.resolve() == args.output.resolve():
        reject("receipt cannot overwrite private key")
    key_id = trust.valid_key_id(args.witness_key_id)
    witness_der = private_signer(args.witness_private_key)
    body, state = current_statement(args.state_dir, key_id, witness_der)
    # Separate signing domain: refuse to use any data-witness key as an
    # independent rollback witness, even if operator knows its private key.
    if any(item["fingerprint_sha256"] == trust.fingerprint(witness_der)
           for item in state["keys"].values()):
        reject("rollback witness key must differ from every registry data key")
    body["checkpoint_nonce_hex"] = secrets.token_hex(16)
    try:
        signature = trust.attestation.openssl(
            "sign", args.witness_private_key, preimage(body)
        )
    except trust.attestation.AttestationError as exc:
        raise WitnessError("external witness signing failed") from exc
    if len(signature) != 64:
        reject("unexpected external Ed25519 signature size")
    write_exclusive(args.output, {
        **body, "signature_base64": base64.b64encode(signature).decode("ascii"),
    })
    print("EXTERNAL STATE RECEIPT CREATED: export off-host and pin independently; NOT published")


def verify(args):
    receipt = read_receipt(args.receipt)
    body = independent_verification(
        receipt, args.trusted_public_key, args.trusted_key_id
    )
    if args.action == "verify-receipt":
        print("EXTERNAL WITNESS SIGNATURE VALID: independent key only; state NOT checked")
        return
    if args.state_dir.resolve() in args.receipt.resolve().parents:
        reject("cannot treat a receipt inside the trust directory as independent")
    current, _state = current_statement(
        args.state_dir, body["witness_key_id"],
        trust.derive_ed25519_public_der(args.trusted_public_key),
    )
    for field in current:
        if current[field] != body[field]:
            reject("TRUST ROLLBACK OR DIVERGENCE: state differs from independently retained receipt")
    print("EXTERNAL STATE WITNESS MATCHES: exact state checkpoint; no import authority")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="action", required=True)
    seal_cmd = modes.add_parser("seal", help="Sign a bounded local state commitment")
    seal_cmd.add_argument("--state-dir", type=Path, required=True)
    seal_cmd.add_argument("--output", type=Path, required=True)
    seal_cmd.add_argument("--witness-key-id", required=True)
    seal_cmd.add_argument("--witness-private-key", type=Path, required=True)

    check = modes.add_parser("check", help="Compare current state to off-host signed reference")
    check.add_argument("--state-dir", type=Path, required=True)
    off = modes.add_parser("verify-receipt", help="Verify receipt signature without local state")
    for cmd in (check, off):
        cmd.add_argument("--receipt", type=Path, required=True)
        cmd.add_argument("--trusted-key-id", required=True)
        cmd.add_argument("--trusted-public-key", type=Path, required=True)

    args = parser.parse_args()
    try:
        if args.action == "seal":
            seal(args)
        else:
            verify(args)
    except (WitnessError, trust.TrustError, OSError, ValueError, TypeError) as exc:
        print("EXTERNAL STATE WITNESS DENIED: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
