#!/usr/bin/env python3
"""Phase 31: offline AES-256-GCM protection of separately signed operator snapshots.

A real, owner-private 32-byte symmetric key is required. There is NO key
escrow, automatic restore, rotation, network endpoint or rollback detection.
A verified detached signature and independently pinned SHA-256 are mandatory
on BOTH encrypt and decrypt, before any unencrypted output is created.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SCHEMA = "nexus.operator.encrypted-snapshot.v1"
MAGIC = b"NEXUS-OPERATOR-ENCRYPTED-SNAPSHOT-V1\n"
MAX_PLAINTEXT = 32 * 1024 * 1024
MAX_ENVELOPE = MAX_PLAINTEXT + 8192
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
NONCE_RE = re.compile(r"[0-9a-f]{24}\Z")
DIR = Path(__file__).resolve().parent


class Denied(ValueError):
    pass


def deny(reason: str) -> None:
    raise Denied(reason)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def load_script(file: str, name: str):
    spec = importlib.util.spec_from_file_location(name, DIR / file)
    if spec is None or spec.loader is None:
        deny("script-unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require_operator() -> None:
    if os.name != "posix" or not sys.platform.startswith("linux") or os.getuid() == 0:
        deny("offline-encryption-requires-unprivileged-linux")


def pin(value: str | None) -> str:
    if type(value) is not str or not SHA_RE.fullmatch(value):
        deny("exact-sha256-pin-required")
    return value


def key_bytes(path: Path, signed) -> bytes:
    value = signed.checked_file(path, 64, private=True)
    if len(value) != 32:
        deny("aes256-key-must-be-32-random-bytes")
    return value


def load_public_signature_and_validate(
    raw: bytes, workspace: str, archive_sha: str, workspace_sha: str,
    signature_file: Path, public_file: Path, signer_sha: str, signed, snapshot
) -> None:
    # The signature validates precise snapshot metadata; complete content,
    # path and journal safety are checked by the existing snapshot validator.
    info = signed.payload(workspace, archive_sha, workspace_sha, signer_sha)
    if sha(raw) != archive_sha:
        deny("source-archive-hash-mismatch")
    metadata, _, _ = snapshot.validate(raw, workspace)
    if metadata["workspace_sha256"] != workspace_sha:
        deny("source-workspace-hash-mismatch")

    public = signed.load_public(public_file)
    if signed.fingerprint(public) != signer_sha:
        deny("independent-signer-pin-mismatch")
    envelope_bytes = signed.checked_file(signature_file, 8192, private=True)
    record = signed.unique_json(envelope_bytes)
    if (set(record) != {"payload", "signature_hex"}
            or type(record["payload"]) is not dict
            or record["payload"] != info
            or canonical(record) != envelope_bytes
            or type(record["signature_hex"]) is not str
            or not signed.SIGNATURE.fullmatch(record["signature_hex"])):
        deny("detached-signature-mismatch")
    try:
        public.verify(bytes.fromhex(record["signature_hex"]),
                      signed.signed_message(info))
    except InvalidSignature as exc:
        raise Denied("detached-signature-invalid") from exc


def parse_envelope(raw: bytes, expected_sealed_sha: str) -> tuple[dict, bytes, bytes]:
    if sha(raw) != pin(expected_sealed_sha):
        deny("encrypted-envelope-sha256-mismatch")
    if not raw.startswith(MAGIC) or len(raw) < len(MAGIC) + 2 + 16:
        deny("encrypted-envelope-format")
    offset = len(MAGIC)
    header_len = int.from_bytes(raw[offset:offset + 2], "big")
    if not 0 < header_len <= 2048 or len(raw) < offset + 2 + header_len + 16:
        deny("encrypted-header-length")
    header_bytes = raw[offset + 2:offset + 2 + header_len]
    ciphertext = raw[offset + 2 + header_len:]
    signed = load_script("nexus-operator-snapshot-signature.py",
                         "nexus_phase31_json_validator")
    header = signed.unique_json(header_bytes)
    if (set(header) != {"schema", "workspace", "archive_sha256",
                        "workspace_sha256", "signer_key_sha256", "nonce_hex"}
            or header["schema"] != SCHEMA
            or canonical(header) != header_bytes
            or type(header["nonce_hex"]) is not str
            or not NONCE_RE.fullmatch(header["nonce_hex"])):
        deny("encrypted-header-invalid")
    return header, raw[:offset + 2 + header_len], ciphertext


def encrypt(archive: Path, archive_sha: str, workspace: str, workspace_sha: str,
            signature_file: Path, public_file: Path, signer_sha: str,
            key_file: Path, output: Path) -> dict:
    require_operator()
    archive_sha, workspace_sha, signer_sha = pin(archive_sha), pin(workspace_sha), pin(signer_sha)
    signed = load_script("nexus-operator-snapshot-signature.py", "nexus_phase31_signed")
    snapshot = load_script("nexus-operator-snapshot.py", "nexus_phase31_snapshot")
    raw = signed.checked_file(archive, MAX_PLAINTEXT, private=True)
    load_public_signature_and_validate(
        raw, workspace, archive_sha, workspace_sha,
        signature_file, public_file, signer_sha, signed, snapshot)
    key = key_bytes(key_file, signed)
    nonce = os.urandom(12)
    header = {"schema": SCHEMA, "workspace": workspace,
              "archive_sha256": archive_sha, "workspace_sha256": workspace_sha,
              "signer_key_sha256": signer_sha, "nonce_hex": nonce.hex()}
    prefix = MAGIC + len(canonical(header)).to_bytes(2, "big") + canonical(header)
    sealed = prefix + AESGCM(key).encrypt(nonce, raw, prefix)
    if len(sealed) > MAX_ENVELOPE:
        deny("encrypted-envelope-size-limit")
    signed.write_private_new(output, sealed)
    return {"schema": SCHEMA, "status": "signed-snapshot-encrypted",
            "encrypted_sha256": sha(sealed),
            "plaintext_sha256": archive_sha,
            "workspace_sha256": workspace_sha,
            "authenticated_encryption": True, "signed_source_verified": True,
            "plaintext_deleted": False, "external_key_custody_verified": False,
            "freshness_protected": False, "production_ready": False,
            "authority": "none"}


def decrypt(sealed_file: Path, expected_sealed_sha: str, archive_sha: str,
            workspace: str, workspace_sha: str, signature_file: Path,
            public_file: Path, signer_sha: str,
            key_file: Path, output: Path) -> dict:
    require_operator()
    archive_sha, workspace_sha, signer_sha = pin(archive_sha), pin(workspace_sha), pin(signer_sha)
    signed = load_script("nexus-operator-snapshot-signature.py", "nexus_phase31_signed")
    snapshot = load_script("nexus-operator-snapshot.py", "nexus_phase31_snapshot")
    sealed = signed.checked_file(sealed_file, MAX_ENVELOPE, private=True)
    header, prefix, ciphertext = parse_envelope(sealed, expected_sealed_sha)
    if (header["workspace"] != workspace
            or header["archive_sha256"] != archive_sha
            or header["workspace_sha256"] != workspace_sha
            or header["signer_key_sha256"] != signer_sha):
        deny("encrypted-context-pin-mismatch")
    key = key_bytes(key_file, signed)
    try:
        raw = AESGCM(key).decrypt(bytes.fromhex(header["nonce_hex"]),
                                  ciphertext, prefix)
    except InvalidTag as exc:
        raise Denied("encrypted-authentication-failed") from exc
    if len(raw) > MAX_PLAINTEXT:
        deny("decrypted-size-limit")
    # Do not write ANY plaintext if authenticity or complete snapshot
    # journal and path verification fails. The output is a private ZIP
    # explicitly retained for separate, manually approved signed restore.
    load_public_signature_and_validate(
        raw, workspace, archive_sha, workspace_sha,
        signature_file, public_file, signer_sha, signed, snapshot)
    signed.write_private_new(output, raw)
    return {"schema": SCHEMA, "status": "signed-snapshot-decrypted-to-private-file",
            "encrypted_sha256": sha(sealed), "plaintext_sha256": sha(raw),
            "workspace_sha256": workspace_sha, "signed_source_verified": True,
            "authenticated_decryption": True, "plaintext_file_created": True,
            "jobs_restarted": False, "freshness_protected": False,
            "external_key_custody_verified": False, "production_ready": False,
            "authority": "none"}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("new-key", "encrypt", "decrypt"))
    p.add_argument("--key", type=Path, required=True)
    p.add_argument("--archive", type=Path)
    p.add_argument("--sealed", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--signature", type=Path)
    p.add_argument("--public-key", type=Path)
    p.add_argument("--workspace")
    p.add_argument("--expected-archive-sha256")
    p.add_argument("--expected-workspace-sha256")
    p.add_argument("--expected-signer-sha256")
    p.add_argument("--expected-sealed-sha256")
    p.add_argument("--approve-new-key", action="store_true")
    p.add_argument("--approve-encrypt", action="store_true")
    p.add_argument("--approve-decrypt", action="store_true")
    a = p.parse_args(argv)
    try:
        require_operator()
        if a.action == "new-key":
            if (not a.approve_new_key or a.approve_encrypt or a.approve_decrypt
                    or any((a.archive, a.sealed, a.output, a.signature, a.public_key,
                            a.workspace, a.expected_archive_sha256,
                            a.expected_workspace_sha256, a.expected_signer_sha256,
                            a.expected_sealed_sha256))):
                deny("new-key-requires-exclusive-approval")
            signed = load_script("nexus-operator-snapshot-signature.py",
                                 "nexus_phase31_key_file")
            signed.write_private_new(a.key, os.urandom(32))
            result = {"schema": SCHEMA, "status": "offline-aes256-key-created",
                      "key_backed_up": False, "production_ready": False,
                      "authority": "none"}
        elif a.action == "encrypt":
            if (not a.approve_encrypt or a.approve_new_key or a.approve_decrypt
                    or not all((a.archive, a.output, a.signature, a.public_key,
                                a.workspace, a.expected_archive_sha256,
                                a.expected_workspace_sha256, a.expected_signer_sha256))
                    or a.sealed or a.expected_sealed_sha256):
                deny("encrypt-requires-explicit-pins-and-approval")
            result = encrypt(
                a.archive, a.expected_archive_sha256, a.workspace,
                a.expected_workspace_sha256, a.signature, a.public_key,
                a.expected_signer_sha256, a.key, a.output)
        else:
            if (not a.approve_decrypt or a.approve_new_key or a.approve_encrypt
                    or not all((a.sealed, a.output, a.signature, a.public_key,
                                a.workspace, a.expected_archive_sha256,
                                a.expected_workspace_sha256, a.expected_signer_sha256,
                                a.expected_sealed_sha256)) or a.archive):
                deny("decrypt-requires-explicit-pins-and-approval")
            result = decrypt(
                a.sealed, a.expected_sealed_sha256, a.expected_archive_sha256,
                a.workspace, a.expected_workspace_sha256, a.signature,
                a.public_key, a.expected_signer_sha256, a.key, a.output)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        # Never print paths, key material, plaintext, signatures or ciphertext.
        print(json.dumps({"status": "denied", "reason": type(exc).__name__,
                          "production_ready": False, "authority": "none"}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
