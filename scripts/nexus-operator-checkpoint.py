#!/usr/bin/env python3
"""Phase 32: operator-authorized latest-checkpoint pins for offline recovery.

A caller MUST independently supply the exact latest checkpoint SHA-256 and
sequence; neither a local file, signature nor the operator's memory can prove
freshness by itself. This tool does not mutate an independent trust store.
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
import tempfile

from cryptography.exceptions import InvalidSignature

SCHEMA = "nexus.operator.recovery-checkpoint.v1"
DOMAIN = b"NEXUS-OPERATOR-RECOVERY-CHECKPOINT-V1\x00"
ZERO = "0" * 64
MAX_SEQUENCE = 2**31 - 1
SHA = re.compile(r"[0-9a-f]{64}\Z")
SIGNATURE = re.compile(r"[0-9a-f]{128}\Z")
BASE = Path(__file__).resolve().parent


class Denied(ValueError):
    pass


def deny(reason: str) -> None:
    raise Denied(reason)


def load_script(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(name, BASE / filename)
    if spec is None or spec.loader is None:
        deny("dependency-unavailable")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def checked_sha(value) -> str:
    if type(value) is not str or not SHA.fullmatch(value):
        deny("trusted-sha256-required")
    return value


def checked_seq(value, *, allow_zero: bool = False) -> int:
    if type(value) is not int or not (0 if allow_zero else 1) <= value <= MAX_SEQUENCE:
        deny("trusted-sequence-required")
    return value


def valid_record(info: object) -> dict:
    required = {"schema", "workspace", "sequence", "previous_sha256",
                "encrypted_sha256", "archive_sha256", "workspace_sha256",
                "snapshot_signer_sha256", "checkpoint_signer_sha256"}
    signed = load_script("nexus-operator-snapshot-signature.py", "nexus_p32_signature")
    if type(info) is not dict or set(info) != required or info["schema"] != SCHEMA:
        deny("checkpoint-schema-invalid")
    signed.require_workspace(info["workspace"])
    checked_seq(info["sequence"])
    for name in required - {"schema", "workspace", "sequence"}:
        checked_sha(info[name])
    if ((info["sequence"] == 1) != (info["previous_sha256"] == ZERO)):
        deny("checkpoint-genesis-inconsistent")
    return info


def read_checkpoint(path: Path, expected_sha: str, trusted_sequence: int,
                    public_key: Path, checkpoint_signer_pin: str) -> dict:
    checked_sha(expected_sha)
    checked_sha(checkpoint_signer_pin)
    checked_seq(trusted_sequence)
    signed = load_script("nexus-operator-snapshot-signature.py", "nexus_p32_verifier")
    raw = signed.checked_file(path, 4096, private=True)
    if sha256(raw) != expected_sha:
        deny("checkpoint-trusted-head-mismatch")
    envelope = signed.unique_json(raw)
    if (set(envelope) != {"payload", "signature_hex"}
            or type(envelope["signature_hex"]) is not str
            or not SIGNATURE.fullmatch(envelope["signature_hex"])
            or canonical(envelope) != raw):
        deny("checkpoint-envelope-invalid")
    info = valid_record(envelope["payload"])
    if (info["sequence"] != trusted_sequence
            or info["checkpoint_signer_sha256"] != checkpoint_signer_pin):
        deny("checkpoint-trusted-sequence-or-signer-mismatch")
    pub = signed.load_public(public_key)
    if signed.fingerprint(pub) != checkpoint_signer_pin:
        deny("checkpoint-public-key-pin-mismatch")
    try:
        pub.verify(bytes.fromhex(envelope["signature_hex"]),
                   DOMAIN + canonical(info))
    except InvalidSignature as exc:
        raise Denied("checkpoint-signature-invalid") from exc
    return info


def verify_encrypted_header(sealed: Path, record: dict) -> None:
    signed = load_script("nexus-operator-snapshot-signature.py", "nexus_p32_sealed")
    encryption = load_script("nexus-operator-snapshot-encryption.py",
                             "nexus_p32_encryption_header")
    raw = signed.checked_file(sealed, encryption.MAX_ENVELOPE, private=True)
    header, _, _ = encryption.parse_envelope(raw, record["encrypted_sha256"])
    expected = {"workspace": record["workspace"],
                "archive_sha256": record["archive_sha256"],
                "workspace_sha256": record["workspace_sha256"],
                "signer_key_sha256": record["snapshot_signer_sha256"]}
    if any(header[key] != value for key, value in expected.items()):
        deny("checkpoint-encrypted-context-mismatch")


def publish(workspace: str, sealed: Path, encrypted_sha: str,
            archive_sha: str, workspace_sha: str, snapshot_signer_sha: str,
            checkpoint_private_key: Path, checkpoint_public_key: Path,
            checkpoint_signer_pin: str, previous_path: Path | None,
            previous_sha: str, previous_sequence: int, output: Path) -> dict:
    signed = load_script("nexus-operator-snapshot-signature.py",
                         "nexus_p32_publisher")
    checked_sha(checkpoint_signer_pin)
    checked_sha(previous_sha)
    checked_seq(previous_sequence, allow_zero=True)
    signed.require_workspace(workspace)
    if previous_sequence == 0:
        if previous_path is not None or previous_sha != ZERO:
            deny("explicit-genesis-required")
    else:
        if previous_path is None or previous_sha == ZERO:
            deny("exact-predecessor-required")
        earlier = read_checkpoint(previous_path, previous_sha, previous_sequence,
                                  checkpoint_public_key, checkpoint_signer_pin)
        if earlier["workspace"] != workspace:
            deny("checkpoint-workspace-changed")
    if previous_sequence >= MAX_SEQUENCE:
        deny("checkpoint-sequence-exhausted")
    record = valid_record({
        "schema": SCHEMA, "workspace": workspace,
        "sequence": previous_sequence + 1, "previous_sha256": previous_sha,
        "encrypted_sha256": checked_sha(encrypted_sha),
        "archive_sha256": checked_sha(archive_sha),
        "workspace_sha256": checked_sha(workspace_sha),
        "snapshot_signer_sha256": checked_sha(snapshot_signer_sha),
        "checkpoint_signer_sha256": checkpoint_signer_pin})
    verify_encrypted_header(sealed, record)
    private = signed.load_private(checkpoint_private_key)
    public = signed.load_public(checkpoint_public_key)
    if (signed.fingerprint(private.public_key()) != checkpoint_signer_pin
            or signed.fingerprint(public) != checkpoint_signer_pin):
        deny("checkpoint-signing-key-pin-mismatch")
    envelope = {"payload": record,
                "signature_hex": private.sign(DOMAIN + canonical(record)).hex()}
    raw = canonical(envelope)
    signed.write_private_new(output, raw)
    return {"status": "checkpoint-signed-not-independently-published",
            "schema": SCHEMA, "checkpoint_sha256": sha256(raw),
            "sequence": record["sequence"],
            "previous_sha256": previous_sha,
            "operator_must_independently_pin_head": True,
            "independent_latest_attested": False,
            "production_ready": False, "authority": "none"}


def check(checkpoint: Path, trusted_head: str, trusted_sequence: int,
          checkpoint_public_key: Path, checkpoint_signer_pin: str,
          sealed: Path | None = None) -> dict:
    record = read_checkpoint(checkpoint, trusted_head, trusted_sequence,
                             checkpoint_public_key, checkpoint_signer_pin)
    if sealed is not None:
        verify_encrypted_header(sealed, record)
    return {"status": "checkpoint-matches-explicit-trusted-head",
            "schema": SCHEMA,
            "checkpoint_sha256": trusted_head,
            "sequence": record["sequence"],
            "encrypted_header_checked": sealed is not None,
            "external_head_source_verified": False,
            "independent_latest_attested": False,
            "production_ready": False, "authority": "none"}


def recover(checkpoint: Path, trusted_head: str, trusted_sequence: int,
            checkpoint_public_key: Path, checkpoint_signer_pin: str,
            sealed: Path, aes_key: Path, snapshot_signature: Path,
            snapshot_public_key: Path, scratch: Path, root: Path) -> dict:
    # Exact independently retained latest head AND sequence are mandatory,
    # before any plaintext material or recovered workspace can be created.
    record = read_checkpoint(checkpoint, trusted_head, trusted_sequence,
                             checkpoint_public_key, checkpoint_signer_pin)
    verify_encrypted_header(sealed, record)
    signed = load_script("nexus-operator-snapshot-signature.py",
                         "nexus_p32_signed_restore")
    snapshot = load_script("nexus-operator-snapshot.py",
                           "nexus_p32_restore_preflight")
    scratch = snapshot.private_root(scratch)
    root = snapshot.private_root(root)
    if any(root.iterdir()):
        deny("recovery-root-must-be-empty")
    # Temporary plaintext lives in owner-private scratch only and is removed
    # on normal return or exception; this is not secure-erasure or crash proof.
    encryption = load_script("nexus-operator-snapshot-encryption.py",
                             "nexus_p32_decryption")
    with tempfile.TemporaryDirectory(prefix="nexus-p32-", dir=scratch) as temp:
        decrypted = Path(temp) / "private-decrypted.zip"
        encryption.decrypt(
            sealed, record["encrypted_sha256"], record["archive_sha256"],
            record["workspace"], record["workspace_sha256"],
            snapshot_signature, snapshot_public_key,
            record["snapshot_signer_sha256"], aes_key, decrypted)
        result = signed.verified_restore(
            root, decrypted, record["archive_sha256"],
            record["workspace"], record["workspace_sha256"],
            snapshot_public_key, record["snapshot_signer_sha256"],
            snapshot_signature)
    if (result["workspace_sha256"] != record["workspace_sha256"]
            or result.get("jobs_restarted") is not False
            or result.get("replay_approvals_transferred") is not True):
        deny("recovery-evidence-mismatch")
    return {"schema": SCHEMA,
            "status": "explicit-trusted-checkpoint-offline-recovery",
            "checkpoint_sha256": trusted_head, "sequence": trusted_sequence,
            "workspace_sha256": result["workspace_sha256"],
            "signed_and_authenticated_encryption_verified": True,
            "finished_receipts_preserved": True,
            "jobs_restarted": False,
            "external_head_source_verified": False,
            "independent_latest_attested": False,
            "secure_plaintext_erase_proven": False,
            "production_ready": False, "authority": "none"}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("publish", "check", "recover"))
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--checkpoint-public-key", type=Path, required=True)
    p.add_argument("--checkpoint-signer-sha256", required=True)
    p.add_argument("--trusted-head-sha256")
    p.add_argument("--trusted-sequence", type=int)
    p.add_argument("--previous-checkpoint", type=Path)
    p.add_argument("--previous-sha256")
    p.add_argument("--previous-sequence", type=int)
    p.add_argument("--checkpoint-private-key", type=Path)
    p.add_argument("--workspace")
    p.add_argument("--sealed", type=Path)
    p.add_argument("--encrypted-sha256")
    p.add_argument("--archive-sha256")
    p.add_argument("--workspace-sha256")
    p.add_argument("--snapshot-signer-sha256")
    p.add_argument("--aes-key", type=Path)
    p.add_argument("--snapshot-signature", type=Path)
    p.add_argument("--snapshot-public-key", type=Path)
    p.add_argument("--scratch", type=Path)
    p.add_argument("--root", type=Path)
    p.add_argument("--approve-publish", action="store_true")
    p.add_argument("--approve-recover", action="store_true")
    a = p.parse_args(argv)
    try:
        if a.action == "publish":
            if (not a.approve_publish or a.approve_recover
                    or any((a.trusted_head_sha256, a.trusted_sequence,
                            a.aes_key, a.snapshot_signature,
                            a.snapshot_public_key, a.scratch, a.root))
                    or not all((a.workspace, a.sealed, a.encrypted_sha256,
                                a.archive_sha256, a.workspace_sha256,
                                a.snapshot_signer_sha256, a.checkpoint_private_key))
                    or a.previous_sequence is None or a.previous_sha256 is None):
                deny("publish-needs-approval-complete-previous-head")
            result = publish(a.workspace, a.sealed, a.encrypted_sha256,
                             a.archive_sha256, a.workspace_sha256,
                             a.snapshot_signer_sha256, a.checkpoint_private_key,
                             a.checkpoint_public_key, a.checkpoint_signer_sha256,
                             a.previous_checkpoint, a.previous_sha256,
                             a.previous_sequence, a.checkpoint)
        elif a.action == "check":
            if (a.approve_publish or a.approve_recover
                    or a.trusted_head_sha256 is None or a.trusted_sequence is None
                    or any((a.checkpoint_private_key, a.previous_checkpoint,
                            a.previous_sha256, a.previous_sequence, a.aes_key,
                            a.snapshot_signature, a.snapshot_public_key,
                            a.scratch, a.root, a.workspace, a.encrypted_sha256,
                            a.archive_sha256, a.workspace_sha256,
                            a.snapshot_signer_sha256))):
                deny("check-requires-independent-exact-head-and-sequence")
            result = check(a.checkpoint, a.trusted_head_sha256, a.trusted_sequence,
                           a.checkpoint_public_key, a.checkpoint_signer_sha256,
                           a.sealed)
        else:
            if (not a.approve_recover or a.approve_publish
                    or a.trusted_head_sha256 is None or a.trusted_sequence is None
                    or not all((a.sealed, a.aes_key, a.snapshot_signature,
                                a.snapshot_public_key, a.scratch, a.root))
                    or any((a.checkpoint_private_key, a.previous_checkpoint,
                            a.previous_sha256, a.previous_sequence, a.workspace,
                            a.encrypted_sha256, a.archive_sha256,
                            a.workspace_sha256, a.snapshot_signer_sha256))):
                deny("recovery-requires-trusted-head-and-explicit-approval")
            result = recover(a.checkpoint, a.trusted_head_sha256,
                             a.trusted_sequence, a.checkpoint_public_key,
                             a.checkpoint_signer_sha256, a.sealed, a.aes_key,
                             a.snapshot_signature, a.snapshot_public_key,
                             a.scratch, a.root)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        # No key, path, signed content or decrypted file bytes in error output.
        print(json.dumps({"status": "denied", "reason": type(exc).__name__,
                          "production_ready": False, "authority": "none"}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
