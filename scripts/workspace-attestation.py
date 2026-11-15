#!/usr/bin/env python3
"""Detached, operator-side Ed25519 witness for exact NEXUS snapshot bytes.

This CLI does NOT grant HTTP import authority, enroll trusted keys, preserve
replay state, or attest that a remote adapter truly executed a machine run.
"""

import argparse
import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

DOMAIN = b"NEXUS\x00workspace-machine-history\x00detached-ed25519\x00v1\x00"
SCHEMA = "nexus.workspace.detached-attestation.v1"
ALGORITHM = "Ed25519"
MAX_SNAPSHOT_BYTES = 16 * 1024 * 1024  # Same limit as Rust durable snapshot store.
MAX_ATTESTATION_BYTES = 8192
REQUIRED_FIELDS = {
    "schema", "algorithm", "key_id", "destination_workspace_id",
    "snapshot_size_bytes", "snapshot_sha256", "signature_base64",
}
KEY_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
HEX_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class AttestationError(Exception):
    pass


def read_bounded(path: Path, limit: int) -> bytes:
    try:
        with path.open("rb") as stream:
            data = stream.read(limit + 1)
    except OSError as exc:
        raise AttestationError("input file not readable") from exc
    if len(data) > limit or not data:
        raise AttestationError("input is empty or exceeds the bounded size")
    return data


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AttestationError("duplicate JSON object key")
        result[key] = value
    return result


def reject_nonfinite(_value):
    raise AttestationError("non-finite JSON numbers are not allowed")


def decode_json(data: bytes):
    try:
        return json.loads(
            data.decode("utf-8"), object_pairs_hook=no_duplicate_keys,
            parse_constant=reject_nonfinite,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AttestationError("invalid UTF-8 JSON") from exc


def checked_token(value: str, kind: str, max_bytes: int = 256) -> bytes:
    if not isinstance(value, str) or not value or not value.strip():
        raise AttestationError(f"missing or empty {kind}")
    encoded = value.encode("utf-8")
    if len(encoded) > max_bytes or any(ord(char) < 32 for char in value):
        raise AttestationError(f"invalid {kind}")
    return encoded


def snapshot_info(raw: bytes) -> str:
    doc = decode_json(raw)
    if not isinstance(doc, dict) or type(doc.get("schema_version")) is not int or doc["schema_version"] != 1:
        raise AttestationError("unsupported snapshot schema")
    workspace = doc.get("workspace")
    events = doc.get("events")
    if not isinstance(workspace, dict) or not isinstance(events, list):
        raise AttestationError("invalid snapshot shape")
    workspace_id = workspace.get("id")
    checked_token(workspace_id, "snapshot workspace ID")
    claims = workspace.get("claims")
    if not isinstance(claims, list):
        raise AttestationError("invalid snapshot claims")
    has_machine_claim = any(
        isinstance(claim, dict) and claim.get("origin") == "MachineAnalysis"
        for claim in claims
    )
    has_machine_event = any(
        isinstance(event, dict) and isinstance(event.get("kind"), dict)
        and "MachineAnalysisRecorded" in event["kind"]
        for event in events
    )
    has_machine_prefix = any(
        isinstance(event, dict) and isinstance(event.get("provenance_id"), str)
        and event["provenance_id"].startswith("machine:")
        for event in events
    )
    if not (has_machine_claim or has_machine_event or has_machine_prefix):
        raise AttestationError("snapshot does not contain machine-history provenance")
    return workspace_id


def message(key_id: str, workspace_id: str, snapshot: bytes) -> bytes:
    # Fixed domain plus four unambiguously length-prefixed fields prevents
    # key-ID substitution, cross-workspace transplant, and content confusion.
    parts = (
        checked_token(key_id, "key ID", 64),
        checked_token(workspace_id, "workspace ID"),
        hashlib.sha256(snapshot).digest(),
        snapshot,
    )
    return DOMAIN + b"".join(len(part).to_bytes(8, "big") + part for part in parts)


def openssl(action: str, key_path: Path, preimage: bytes, signature: bytes = b"") -> bytes:
    with tempfile.TemporaryDirectory(prefix="nexus-attestation-") as folder:
        root = Path(folder)
        preimage_file = root / "preimage.bin"
        preimage_file.write_bytes(preimage)
        os.chmod(preimage_file, 0o600)
        sig_file = root / "signature.bin"
        if action == "verify":
            sig_file.write_bytes(signature)
            os.chmod(sig_file, 0o600)
            command = [
                "openssl", "pkeyutl", "-verify", "-rawin", "-pubin",
                "-inkey", str(key_path), "-in", str(preimage_file),
                "-sigfile", str(sig_file),
            ]
        else:
            command = [
                "openssl", "pkeyutl", "-sign", "-rawin",
                "-inkey", str(key_path), "-in", str(preimage_file),
                "-out", str(sig_file),
            ]
        try:
            result = subprocess.run(command, capture_output=True, timeout=30, check=False)
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
            raise AttestationError("OpenSSL could not run") from exc
        if result.returncode != 0:
            raise AttestationError("Ed25519 signature operation failed")
        return sig_file.read_bytes() if action == "sign" else b""


def store_new_attestation(path: Path, doc: dict):
    contents = (json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    # Never overwrite an existing witness. In particular, no silently updated
    # signature can conceal an earlier signed revision.
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as exc:
        raise AttestationError("attestation destination already exists or is unwritable") from exc
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise


def do_sign(args):
    raw = read_bounded(args.snapshot, MAX_SNAPSHOT_BYTES)
    real_workspace = snapshot_info(raw)
    if real_workspace != args.workspace_id:
        raise AttestationError("destination workspace differs from signed snapshot")
    if not KEY_ID.fullmatch(args.key_id):
        raise AttestationError("invalid key ID")
    if not args.private_key.is_file():
        raise AttestationError("operator private key unavailable")
    sig = openssl("sign", args.private_key, message(args.key_id, real_workspace, raw))
    if len(sig) != 64:
        raise AttestationError("unexpected Ed25519 signature size")
    doc = {
        "schema": SCHEMA,
        "algorithm": ALGORITHM,
        "key_id": args.key_id,
        "destination_workspace_id": real_workspace,
        "snapshot_size_bytes": len(raw),
        "snapshot_sha256": hashlib.sha256(raw).hexdigest(),
        "signature_base64": base64.b64encode(sig).decode("ascii"),
    }
    store_new_attestation(args.output, doc)
    print("DETACHED ATTESTATION CREATED: local operator signing only; import authority unchanged")


def do_verify(args):
    raw = read_bounded(args.snapshot, MAX_SNAPSHOT_BYTES)
    workspace_id = snapshot_info(raw)
    if workspace_id != args.expected_workspace_id:
        raise AttestationError("destination workspace mismatch")
    att = decode_json(read_bounded(args.attestation, MAX_ATTESTATION_BYTES))
    if not isinstance(att, dict) or set(att) != REQUIRED_FIELDS:
        raise AttestationError("invalid attestation envelope fields")
    if att["schema"] != SCHEMA or att["algorithm"] != ALGORITHM:
        raise AttestationError("unsupported attestation version or algorithm")
    if not KEY_ID.fullmatch(args.trusted_key_id):
        raise AttestationError("invalid trusted key ID")
    if att["key_id"] != args.trusted_key_id:
        raise AttestationError("untrusted or substituted key ID")
    if att["destination_workspace_id"] != args.expected_workspace_id:
        raise AttestationError("attested destination mismatch")
    if type(att["snapshot_size_bytes"]) is not int or att["snapshot_size_bytes"] != len(raw):
        raise AttestationError("attested snapshot size mismatch")
    if not isinstance(att["snapshot_sha256"], str) or not HEX_SHA256.fullmatch(att["snapshot_sha256"]):
        raise AttestationError("invalid attested SHA-256 value")
    if att["snapshot_sha256"] != hashlib.sha256(raw).hexdigest():
        raise AttestationError("attested snapshot digest mismatch")
    if not isinstance(att["signature_base64"], str):
        raise AttestationError("invalid signature encoding")
    try:
        signature = base64.b64decode(att["signature_base64"], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise AttestationError("invalid signature encoding") from exc
    if len(signature) != 64:
        raise AttestationError("invalid Ed25519 signature size")
    if not args.trusted_public_key.is_file():
        raise AttestationError("operator-selected public key unavailable")
    openssl(
        "verify", args.trusted_public_key,
        message(att["key_id"], args.expected_workspace_id, raw), signature,
    )
    print("DETACHED SIGNATURE VERIFIED: exact bytes and selected key; NOT authorized for NEXUS import")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    sign = modes.add_parser("sign", help="Operator signs explicit snapshot with an external private key")
    sign.add_argument("--snapshot", type=Path, required=True)
    sign.add_argument("--workspace-id", required=True)
    sign.add_argument("--key-id", required=True)
    sign.add_argument("--private-key", type=Path, required=True)
    sign.add_argument("--output", type=Path, required=True)
    verify = modes.add_parser("verify", help="Verify exact bytes against operator-selected public key")
    verify.add_argument("--snapshot", type=Path, required=True)
    verify.add_argument("--attestation", type=Path, required=True)
    verify.add_argument("--expected-workspace-id", required=True)
    verify.add_argument("--trusted-key-id", required=True)
    verify.add_argument("--trusted-public-key", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.mode == "sign":
            do_sign(args)
        else:
            do_verify(args)
    except AttestationError as exc:
        print("ATTESTATION DENIED: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
