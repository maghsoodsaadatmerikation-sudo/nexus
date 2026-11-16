#!/usr/bin/env python3
"""Phase 30: offline, trust-pin-required Ed25519 signatures for operator snapshots.

This opt-in local CLI does not activate a hosted backup service. A verified
signature proves possession of a key matching an independently supplied pin,
NOT the real-world identity of its holder or protection against rollback.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
import zipfile

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)

SCHEMA = "nexus.operator.snapshot-signature.v1"
SNAPSHOT_SCHEMA = "nexus.operator.offline-snapshot.v1"
DOMAIN = b"NEXUS-OPERATOR-SNAPSHOT-SIGNATURE-V1\\0"
SHA = re.compile(r"[0-9a-f]{64}\\Z")
SIGNATURE = re.compile(r"[0-9a-f]{128}\\Z")
WORKSPACE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\\Z")
MAX_ARCHIVE = 32 * 1024 * 1024


class Denied(ValueError):
    pass


def fail(reason: str) -> None:
    raise Denied(reason)


def canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def require_sha(value: str | None) -> str:
    if type(value) is not str or not SHA.fullmatch(value):
        fail("exact-sha256-required")
    return value


def require_workspace(value: str) -> str:
    if type(value) is not str or not WORKSPACE.fullmatch(value):
        fail("invalid-workspace")
    return value


def checked_file(path: Path, limit: int, *, private: bool) -> bytes:
    # Reject final-component symlinks, hardlinks and special files before read.
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    fd = os.open(path, flags)
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid()
                or st.st_nlink != 1 or st.st_size > limit
                or (private and st.st_mode & 0o077)):
            fail("unsafe-input-file")
        buf = bytearray()
        while len(buf) <= limit:
            data = os.read(fd, min(65536, limit + 1 - len(buf)))
            if not data:
                return bytes(buf)
            buf.extend(data)
        fail("input-too-large")
    finally:
        os.close(fd)


def write_private_new(path: Path, data: bytes) -> None:
    # Never overwrite an existing detached signature or follow a leaf link.
    parent = path.parent
    pfd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY |
                  os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        st = os.fstat(pfd)
        if (st.st_uid != os.getuid() or st.st_mode & 0o077
                or not stat.S_ISDIR(st.st_mode)):
            fail("unsafe-output-directory")
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                     os.O_CLOEXEC | os.O_NOFOLLOW, 0o600, dir_fd=pfd)
        try:
            with os.fdopen(fd, "wb", closefd=False) as dest:
                dest.write(data)
                dest.flush()
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(pfd)
    finally:
        os.close(pfd)


def unique_json(raw: bytes) -> dict:
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                fail("duplicate-json-key")
            obj[key] = value
        return obj
    try:
        obj = json.loads(raw, object_pairs_hook=unique,
                         parse_constant=lambda _: fail("nonfinite-json"))
    except (UnicodeError, RecursionError, ValueError) as exc:
        raise Denied("invalid-json") from exc
    if type(obj) is not dict:
        fail("json-object-required")
    return obj


def snapshot_header(raw: bytes, workspace: str, workspace_sha: str) -> None:
    # Cheap signed-metadata preflight only. Full ZIP/journal validation still
    # happens in the existing snapshot.restore implementation.
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        items = [item for item in z.infolist() if item.filename == "snapshot.json"]
        if (len(items) != 1 or items[0].file_size > 65536
                or items[0].compress_type != zipfile.ZIP_STORED):
            fail("snapshot-metadata-missing")
        meta = unique_json(z.read(items[0]))
        if (meta.get("schema") != SNAPSHOT_SCHEMA
                or meta.get("workspace") != workspace
                or meta.get("workspace_sha256") != workspace_sha):
            fail("snapshot-header-mismatch")


def read_archive(path: Path, expected_sha: str, workspace: str,
                 workspace_sha: str) -> bytes:
    raw = checked_file(path, MAX_ARCHIVE, private=True)
    if digest(raw) != require_sha(expected_sha):
        fail("archive-digest-mismatch")
    snapshot_header(raw, workspace, workspace_sha)
    return raw


def load_private(path: Path) -> Ed25519PrivateKey:
    private = serialization.load_pem_private_key(
        checked_file(path, 8192, private=True), password=None)
    if not isinstance(private, Ed25519PrivateKey):
        fail("ed25519-private-key-required")
    return private


def load_public(path: Path) -> Ed25519PublicKey:
    public = serialization.load_pem_public_key(
        checked_file(path, 8192, private=False))
    if not isinstance(public, Ed25519PublicKey):
        fail("ed25519-public-key-required")
    return public


def fingerprint(public: Ed25519PublicKey) -> str:
    return digest(public.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw))


def payload(workspace: str, archive_sha: str, workspace_sha: str,
            signer_pin: str) -> dict:
    return {"schema": SCHEMA, "workspace": require_workspace(workspace),
            "archive_sha256": require_sha(archive_sha),
            "workspace_sha256": require_sha(workspace_sha),
            "signer_key_sha256": require_sha(signer_pin)}


def signed_message(info: dict) -> bytes:
    return DOMAIN + canonical(info)


def sign(archive: Path, archive_sha: str, workspace: str, workspace_sha: str,
         private_key: Path, signer_pin: str, signature_file: Path) -> dict:
    info = payload(workspace, archive_sha, workspace_sha, signer_pin)
    read_archive(archive, archive_sha, workspace, workspace_sha)
    key = load_private(private_key)
    if fingerprint(key.public_key()) != signer_pin:
        fail("signer-public-key-pin-mismatch")
    signature = key.sign(signed_message(info)).hex()
    write_private_new(signature_file,
                      canonical({"payload": info, "signature_hex": signature}))
    return {"status": "detached-signature-created", "schema": SCHEMA,
            "signer_key_sha256": signer_pin, "signature_validated": False,
            "publisher_identity_independently_attested": False,
            "backup_encrypted": False, "production_ready": False,
            "authority": "none"}


def verify(archive: Path, archive_sha: str, workspace: str,
           workspace_sha: str, public_key: Path, signer_pin: str,
           signature_file: Path) -> dict:
    info = payload(workspace, archive_sha, workspace_sha, signer_pin)
    pub = load_public(public_key)
    if fingerprint(pub) != signer_pin:
        fail("untrusted-public-key")
    envelope_bytes = checked_file(signature_file, 8192, private=True)
    envelope = unique_json(envelope_bytes)
    if (set(envelope) != {"payload", "signature_hex"}
            or type(envelope["payload"]) is not dict
            or envelope["payload"] != info
            or type(envelope["signature_hex"]) is not str
            or not SIGNATURE.fullmatch(envelope["signature_hex"])
            or canonical(envelope) != envelope_bytes):
        fail("signature-envelope-mismatch")
    try:
        pub.verify(bytes.fromhex(envelope["signature_hex"]),
                   signed_message(info))
    except InvalidSignature as exc:
        raise Denied("invalid-signature") from exc
    read_archive(archive, archive_sha, workspace, workspace_sha)
    return {"status": "detached-signature-verified", "schema": SCHEMA,
            "archive_sha256": archive_sha, "workspace_sha256": workspace_sha,
            "signer_key_sha256": signer_pin, "signature_validated": True,
            "publisher_identity_independently_attested": False,
            "backup_encrypted": False, "production_ready": False,
            "authority": "none"}


def verified_restore(root: Path, archive: Path, archive_sha: str,
                     workspace: str, workspace_sha: str, public_key: Path,
                     signer_pin: str, signature_file: Path) -> dict:
    verification = verify(archive, archive_sha, workspace, workspace_sha,
                          public_key, signer_pin, signature_file)
    # Re-use the existing fail-closed full manifest/journal validator before
    # creating any destination. The existing restore rechecks SHA before writes.
    source = Path(__file__).with_name("nexus-operator-snapshot.py")
    spec = importlib.util.spec_from_file_location("nexus_verified_snapshot", source)
    if spec is None or spec.loader is None:
        fail("snapshot-implementation-unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw = module.checked_archive(archive, archive_sha)
    meta, _, _ = module.validate(raw, workspace)
    if meta["workspace_sha256"] != workspace_sha:
        fail("workspace-pin-mismatch")
    restored = module.restore(root, workspace, archive, archive_sha)
    if restored.get("workspace_sha256") != workspace_sha:
        fail("restored-workspace-hash-mismatch")
    return {**restored, "status": "verified-signed-offline-restore",
            "signature_validated": verification["signature_validated"],
            "signer_key_sha256": signer_pin,
            "publisher_identity_independently_attested": False,
            "backup_encrypted": False, "production_ready": False,
            "authority": "none"}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("sign", "verify", "restore"))
    p.add_argument("--archive", required=True, type=Path)
    p.add_argument("--expected-archive-sha256", required=True)
    p.add_argument("--workspace", required=True)
    p.add_argument("--expected-workspace-sha256", required=True)
    p.add_argument("--signature", required=True, type=Path)
    p.add_argument("--expected-signer-sha256", required=True)
    p.add_argument("--private-key", type=Path)
    p.add_argument("--public-key", type=Path)
    p.add_argument("--root", type=Path)
    p.add_argument("--approve-offline-sign", action="store_true")
    p.add_argument("--approve-offline-restore", action="store_true")
    a = p.parse_args(argv)
    try:
        if a.action == "sign":
            if (not a.approve_offline_sign or a.approve_offline_restore
                    or not a.private_key or a.public_key or a.root):
                fail("sign-requires-explicit-approval-private-key")
            result = sign(a.archive, a.expected_archive_sha256, a.workspace,
                          a.expected_workspace_sha256, a.private_key,
                          a.expected_signer_sha256, a.signature)
        elif a.action == "verify":
            if (a.private_key or a.root or a.approve_offline_sign
                    or a.approve_offline_restore or not a.public_key):
                fail("verify-accepts-public-key-only")
            result = verify(a.archive, a.expected_archive_sha256, a.workspace,
                            a.expected_workspace_sha256, a.public_key,
                            a.expected_signer_sha256, a.signature)
        else:
            if (not a.root or not a.public_key or a.private_key
                    or not a.approve_offline_restore or a.approve_offline_sign):
                fail("restore-requires-explicit-approval-trust-pin-and-root")
            result = verified_restore(
                a.root, a.archive, a.expected_archive_sha256, a.workspace,
                a.expected_workspace_sha256, a.public_key,
                a.expected_signer_sha256, a.signature)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        # Fail closed without printing filesystem paths, keys or exception text.
        print(json.dumps({"status": "denied", "reason": type(exc).__name__,
                          "authority": "none", "production_ready": False}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
