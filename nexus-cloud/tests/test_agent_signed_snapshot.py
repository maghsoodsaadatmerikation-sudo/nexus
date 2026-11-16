"""Phase 30: real Ed25519 pin, signature and signed recovery, synthetic only.

The signing key is disposable test data, NOT a real publisher identity.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def load(name, key):
    spec = importlib.util.spec_from_file_location(key, SCRIPTS / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


signed = load("nexus-operator-snapshot-signature.py", "nexus_signed_snapshot_tests")
cross = load("test-operator-cross-runner.py", "nexus_cross_runner_signed_tests")


@pytest.fixture
def case(tmp_path):
    if os.getuid() == 0:
        pytest.skip("snapshot recovery requires a nonroot Linux UID")
    src = tmp_path / "producer"
    src.mkdir(mode=0o700)
    receipt = cross.produce(src)
    archive = src / "transfer" / "snapshot.zip"

    keys = tmp_path / "keys"
    keys.mkdir(mode=0o700)
    private = Ed25519PrivateKey.generate()
    secret = keys / "producer-private.pem"
    secret.write_bytes(private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()))
    secret.chmod(0o600)
    public = keys / "approved-public.pem"
    public.write_bytes(private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo))
    public.chmod(0o644)
    pin = signed.fingerprint(private.public_key())
    out = keys / "signature.json"
    fields = {"archive": archive, "archive_sha": receipt["snapshot_sha256"],
              "workspace": cross.WORKSPACE,
              "workspace_sha": receipt["workspace_sha256"],
              "public": public, "private": secret, "pin": pin, "signature": out}
    return fields


def sign(case):
    return signed.sign(case["archive"], case["archive_sha"], case["workspace"],
                       case["workspace_sha"], case["private"], case["pin"],
                       case["signature"])


def verify(case, **updates):
    details = {**case, **updates}
    return signed.verify(details["archive"], details["archive_sha"],
                         details["workspace"], details["workspace_sha"],
                         details["public"], details["pin"], details["signature"])


def test_signature_and_full_offline_recovery_preserve_consumed_receipt(case, tmp_path):
    result = sign(case)
    assert result["status"] == "detached-signature-created"
    assert result["publisher_identity_independently_attested"] is False
    assert case["signature"].stat().st_mode & 0o077 == 0
    assert verify(case)["signature_validated"] is True
    root = tmp_path / "restored"
    root.mkdir(mode=0o700)
    restored = signed.verified_restore(
        root, case["archive"], case["archive_sha"], case["workspace"],
        case["workspace_sha"], case["public"], case["pin"], case["signature"])
    assert restored["status"] == "verified-signed-offline-restore"
    assert restored["signature_validated"] is True
    assert restored["backup_encrypted"] is False
    assert restored["production_ready"] is False
    workspace = cross.Workspace(root, cross.WORKSPACE)
    assert workspace.read("input.txt") == cross.INPUT
    assert workspace.read("result.txt") == cross.OUTPUT
    journal = cross.ApprovalJournal(workspace)
    record = journal.read(cross.DIGEST)
    assert record["state"] == "finished"
    with pytest.raises(cross.WorkspaceDenied):
        journal.claim(cross.DIGEST, version=3,
                      workspace_before=record["workspace_sha256_before"],
                      execution_nonce="d" * 32)
    assert journal.read(cross.DIGEST) == record


def test_modified_archive_even_with_new_digest_is_rejected_before_restore(case, tmp_path):
    sign(case)
    mutated = tmp_path / "tampered.zip"
    raw = bytearray(case["archive"].read_bytes())
    offset = raw.find(cross.OUTPUT)
    assert offset > 0
    raw[offset] ^= 1
    mutated.write_bytes(raw)
    mutated.chmod(0o600)
    digest = hashlib.sha256(raw).hexdigest()
    with pytest.raises(signed.Denied, match="signature-envelope-mismatch"):
        verify(case, archive=mutated, archive_sha=digest)
    root = tmp_path / "empty"
    root.mkdir(mode=0o700)
    with pytest.raises(signed.Denied):
        signed.verified_restore(root, mutated, digest, case["workspace"],
                                case["workspace_sha"], case["public"],
                                case["pin"], case["signature"])
    assert not list(root.iterdir())


def test_wrong_public_key_and_unpinned_key_denied(case):
    sign(case)
    other = Ed25519PrivateKey.generate()
    fake = case["public"].parent / "other-public.pem"
    fake.write_bytes(other.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    assert signed.fingerprint(other.public_key()) != case["pin"]
    with pytest.raises(signed.Denied, match="untrusted-public-key"):
        verify(case, public=fake)
    with pytest.raises(signed.Denied, match="untrusted-public-key"):
        verify(case, pin="0" * 64)


def test_modified_signature_and_wrong_workspace_denied(case):
    sign(case)
    envelope = json.loads(case["signature"].read_text())
    envelope["signature_hex"] = "0" * 128
    case["signature"].write_bytes(signed.canonical(envelope))
    with pytest.raises(signed.Denied, match="invalid-signature"):
        verify(case)
    with pytest.raises(signed.Denied, match="signature-envelope-mismatch"):
        verify(case, workspace_sha="1" * 64)


def test_duplicate_json_keys_and_noncanonical_envelope_denied(case):
    sign(case)
    valid = case["signature"].read_bytes()
    duplicated = b'{"payload":{}, "payload":{}, "signature_hex":"' + b"0"*128 + b'"}'
    case["signature"].write_bytes(duplicated)
    with pytest.raises(signed.Denied, match="invalid-json"):
        verify(case)
    case["signature"].write_bytes(valid + b" ")
    with pytest.raises(signed.Denied, match="signature-envelope-mismatch"):
        verify(case)


def test_symlink_signature_and_insecure_private_key_denied(case, tmp_path):
    sign(case)
    alias = tmp_path / "signature-link"
    alias.symlink_to(case["signature"])
    with pytest.raises(OSError):
        verify(case, signature=alias)
    case["private"].chmod(0o644)
    alias_signature = case["signature"].parent / "next-signature.json"
    with pytest.raises(signed.Denied, match="unsafe-input-file"):
        signed.sign(case["archive"], case["archive_sha"], case["workspace"],
                    case["workspace_sha"], case["private"], case["pin"],
                    alias_signature)
    assert not alias_signature.exists()


def test_signature_cannot_be_overwritten_and_failed_restore_leaves_original(case, tmp_path):
    sign(case)
    with pytest.raises(FileExistsError):
        sign(case)
    original = tmp_path / "nonempty"
    original.mkdir(mode=0o700)
    (original / "preserve.txt").write_text("user data")
    with pytest.raises(Exception):
        signed.verified_restore(original, case["archive"], case["archive_sha"],
                                case["workspace"], case["workspace_sha"],
                                case["public"], case["pin"], case["signature"])
    assert (original / "preserve.txt").read_text() == "user data"


def test_cli_explicit_approval_and_pin_required(case, tmp_path, capsys):
    args = ["sign", "--archive", str(case["archive"]),
            "--expected-archive-sha256", case["archive_sha"],
            "--workspace", case["workspace"],
            "--expected-workspace-sha256", case["workspace_sha"],
            "--private-key", str(case["private"]),
            "--signature", str(case["signature"]),
            "--expected-signer-sha256", case["pin"]]
    assert signed.main(args) == 2
    assert not case["signature"].exists()
    assert signed.main(args + ["--approve-offline-sign"]) == 0
    dest = tmp_path / "empty"
    dest.mkdir(mode=0o700)
    verify_args = ["--archive", str(case["archive"]),
                   "--expected-archive-sha256", case["archive_sha"],
                   "--workspace", case["workspace"],
                   "--expected-workspace-sha256", case["workspace_sha"],
                   "--public-key", str(case["public"]),
                   "--signature", str(case["signature"]),
                   "--expected-signer-sha256", case["pin"]]
    assert signed.main(["restore", *verify_args, "--root", str(dest)]) == 2
    assert not list(dest.iterdir())
    assert signed.main(["verify", *verify_args]) == 0
    out = capsys.readouterr()
    assert "PRIVATE KEY" not in out.out and str(case["private"]) not in out.out
    assert "production_ready" in out.out
