"""Phase 31: synthetic offline encrypted, signed snapshot acceptance.

Only disposable keys, files and local scratch. No production snapshots.
Cryptography is optional for broad Cloud Adapter jobs and mandatory in the
dedicated phase-31 workflow; this skip MUST NOT occur in dedicated CI.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest

pytest.importorskip("cryptography", reason="operator cryptography tested in dedicated CI")
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def load(file, name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


encryption = load("nexus-operator-snapshot-encryption.py", "nexus_encryption_tests")
signed = load("nexus-operator-snapshot-signature.py", "nexus_signing_for_encryption_tests")
cross = load("test-operator-cross-runner.py", "nexus_cross_runner_for_encryption_tests")


@pytest.fixture
def case(tmp_path):
    if os.getuid() == 0:
        pytest.skip("operator encryption requires nonroot Linux")
    source_root = tmp_path / "source"
    source_root.mkdir(mode=0o700)
    source = cross.produce(source_root)
    archive = source_root / "transfer" / "snapshot.zip"
    secrets = tmp_path / "secrets"
    secrets.mkdir(mode=0o700)
    private = Ed25519PrivateKey.generate()
    secret_file = secrets / "signing-private.pem"
    secret_file.write_bytes(private.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()))
    secret_file.chmod(0o600)
    public_file = secrets / "signing-public.pem"
    public_file.write_bytes(private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    signer_pin = signed.fingerprint(private.public_key())
    signature = secrets / "signature.json"
    signed.sign(archive, source["snapshot_sha256"], cross.WORKSPACE,
                source["workspace_sha256"], secret_file, signer_pin, signature)
    key = secrets / "aes256.key"
    signed.write_private_new(key, os.urandom(32))
    sealed = secrets / "encrypted.snapshot"
    plaintext = secrets / "decrypted.zip"
    return {"archive": archive, "archive_sha": source["snapshot_sha256"],
            "workspace": cross.WORKSPACE, "workspace_sha": source["workspace_sha256"],
            "public": public_file, "signer": signer_pin, "signature": signature,
            "key": key, "sealed": sealed, "plain": plaintext, "tmp": tmp_path}


def encrypt(c, **overrides):
    a = {**c, **overrides}
    return encryption.encrypt(a["archive"], a["archive_sha"], a["workspace"],
                              a["workspace_sha"], a["signature"], a["public"],
                              a["signer"], a["key"], a["sealed"])


def decrypt(c, sealed_sha, **overrides):
    a = {**c, **overrides}
    return encryption.decrypt(a["sealed"], sealed_sha, a["archive_sha"],
                              a["workspace"], a["workspace_sha"],
                              a["signature"], a["public"], a["signer"],
                              a["key"], a["plain"])


def test_encrypt_roundtrip_signed_recovery_and_no_output_overwrite(case):
    result = encrypt(case)
    assert result["status"] == "signed-snapshot-encrypted"
    assert result["authenticated_encryption"] is True
    assert result["plaintext_deleted"] is False
    encrypted_bytes = case["sealed"].read_bytes()
    assert cross.INPUT not in encrypted_bytes
    assert cross.OUTPUT not in encrypted_bytes
    assert encrypted_bytes.startswith(encryption.MAGIC)
    assert case["sealed"].stat().st_mode & 0o077 == 0
    assert result["encrypted_sha256"] == hashlib.sha256(encrypted_bytes).hexdigest()
    with pytest.raises(FileExistsError):
        encrypt(case)
    restored = decrypt(case, result["encrypted_sha256"])
    assert restored["status"] == "signed-snapshot-decrypted-to-private-file"
    assert restored["signed_source_verified"] is True
    assert restored["plaintext_file_created"] is True
    assert restored["freshness_protected"] is False
    assert case["plain"].stat().st_mode & 0o077 == 0
    assert case["plain"].read_bytes() == case["archive"].read_bytes()
    with pytest.raises(FileExistsError):
        decrypt(case, result["encrypted_sha256"])
    receiver = case["tmp"] / "restored-root"
    receiver.mkdir(mode=0o700)
    report = signed.verified_restore(receiver, case["plain"], case["archive_sha"],
                                     case["workspace"], case["workspace_sha"],
                                     case["public"], case["signer"], case["signature"])
    assert report["signature_validated"] is True
    ws = cross.Workspace(receiver, cross.WORKSPACE)
    assert ws.read("result.txt") == cross.OUTPUT
    ledger = cross.ApprovalJournal(ws)
    record = ledger.read(cross.DIGEST)
    with pytest.raises(cross.WorkspaceDenied):
        ledger.claim(cross.DIGEST, version=3,
                     workspace_before=record["workspace_sha256_before"],
                     execution_nonce="d" * 32)


def test_wrong_encryption_key_and_missing_pin_fail_before_plaintext(case):
    result = encrypt(case)
    bad_key = case["tmp"] / "secrets" / "other.key"
    signed.write_private_new(bad_key, os.urandom(32))
    with pytest.raises(encryption.Denied, match="encrypted-authentication-failed"):
        decrypt(case, result["encrypted_sha256"], key=bad_key)
    with pytest.raises(encryption.Denied, match="encrypted-envelope-sha256-mismatch"):
        decrypt(case, "0" * 64)
    assert not case["plain"].exists()


def test_ciphertext_tamper_even_with_new_outer_sha_fails_authentication(case):
    encrypt(case)
    raw = bytearray(case["sealed"].read_bytes())
    raw[-18] ^= 1
    forged = case["tmp"] / "secrets" / "changed.snapshot"
    signed.write_private_new(forged, bytes(raw))
    new_sha = hashlib.sha256(raw).hexdigest()
    with pytest.raises(encryption.Denied, match="encrypted-authentication-failed"):
        decrypt(case, new_sha, sealed=forged)
    assert not case["plain"].exists()


def test_wrong_signature_and_wrong_signer_pin_do_not_produce_encrypted_file(case):
    record = json.loads(case["signature"].read_text())
    record["signature_hex"] = "0" * 128
    case["signature"].write_bytes(signed.canonical(record))
    with pytest.raises(encryption.Denied, match="detached-signature-invalid"):
        encrypt(case)
    assert not case["sealed"].exists()
    with pytest.raises(encryption.Denied, match="independent-signer-pin-mismatch"):
        encrypt(case, signer="0" * 64)
    assert not case["sealed"].exists()


def test_signature_and_workspace_pins_rechecked_before_plaintext_output(case):
    result = encrypt(case)
    with pytest.raises(encryption.Denied, match="encrypted-context-pin-mismatch"):
        decrypt(case, result["encrypted_sha256"], workspace_sha="1" * 64)
    record = json.loads(case["signature"].read_text())
    record["signature_hex"] = "0" * 128
    case["signature"].write_bytes(signed.canonical(record))
    with pytest.raises(encryption.Denied, match="detached-signature-invalid"):
        decrypt(case, result["encrypted_sha256"])
    assert not case["plain"].exists()


def test_modified_authenticated_header_with_recomputed_digest_is_denied(case):
    encrypt(case)
    raw = bytearray(case["sealed"].read_bytes())
    idx = raw.find(b"encrypted-snapshot.v1")
    assert idx > 0
    raw[idx] ^= 1
    altered = case["tmp"] / "secrets" / "wrong-header.snapshot"
    signed.write_private_new(altered, bytes(raw))
    with pytest.raises(encryption.Denied):
        decrypt(case, hashlib.sha256(raw).hexdigest(), sealed=altered)
    assert not case["plain"].exists()


def test_key_file_must_be_private_regular_unlinked_and_32_bytes(case):
    case["key"].chmod(0o644)
    with pytest.raises(signed.WorkspaceDenied if hasattr(signed, "WorkspaceDenied") else Exception):
        encrypt(case)
    case["key"].chmod(0o600)
    linked = case["tmp"] / "secrets" / "key-symlink"
    linked.symlink_to(case["key"])
    with pytest.raises(OSError):
        encrypt(case, key=linked)
    with pytest.raises(encryption.Denied, match="aes256-key-must-be-32-random-bytes"):
        short = case["tmp"] / "secrets" / "short-key"
        signed.write_private_new(short, os.urandom(24))
        encrypt(case, key=short)
    assert not case["sealed"].exists()


def test_keygen_requires_explicit_approval_and_never_replaces_existing_key(case, capsys):
    new_key = case["tmp"] / "secrets" / "generated.key"
    assert encryption.main(["new-key", "--key", str(new_key)]) == 2
    assert not new_key.exists()
    assert encryption.main(["new-key", "--key", str(new_key),
                            "--approve-new-key"]) == 0
    assert len(new_key.read_bytes()) == 32
    assert new_key.stat().st_mode & 0o077 == 0
    assert encryption.main(["new-key", "--key", str(new_key),
                            "--approve-new-key"]) == 2
    transcript = capsys.readouterr()
    assert "offline-aes256-key-created" in transcript.out
    assert str(new_key) not in transcript.out


def test_decrypt_cli_requires_sealed_sha_and_individual_consent(case):
    result = encrypt(case)
    argv = ["decrypt", "--key", str(case["key"]),
            "--sealed", str(case["sealed"]),
            "--output", str(case["plain"]),
            "--signature", str(case["signature"]),
            "--public-key", str(case["public"]),
            "--workspace", case["workspace"],
            "--expected-archive-sha256", case["archive_sha"],
            "--expected-workspace-sha256", case["workspace_sha"],
            "--expected-signer-sha256", case["signer"]]
    assert encryption.main(argv + ["--approve-decrypt"]) == 2
    assert not case["plain"].exists()
    assert encryption.main(argv + ["--expected-sealed-sha256",
                                   result["encrypted_sha256"]]) == 2
    assert not case["plain"].exists()
    assert encryption.main(argv + ["--expected-sealed-sha256",
                                   result["encrypted_sha256"],
                                   "--approve-decrypt"]) == 0
    assert case["plain"].is_file()


def test_unsigned_snapshot_cannot_be_sealed(case):
    case["signature"].unlink()
    with pytest.raises(OSError):
        encrypt(case)
    assert not case["sealed"].exists()
