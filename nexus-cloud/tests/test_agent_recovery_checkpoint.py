"""Phase 32: signed head checkpoints and exact-pin recovery (synthetic only).

The actual trusted head comes from the operator's independent record, NOT
from CI, a mutable local state file or the snapshot itself.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest

pytest.importorskip("cryptography", reason="operator cryptography is gated in dedicated CI")
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checkpoint = load("nexus-operator-checkpoint.py", "nexus_p32_checkpoints_test")
signed = load("nexus-operator-snapshot-signature.py", "nexus_p32_snapshot_sign_test")
encrypted = load("nexus-operator-snapshot-encryption.py", "nexus_p32_encrypt_test")
cross = load("test-operator-cross-runner.py", "nexus_p32_synthetic_test")


def generate_signer(directory, name):
    key = Ed25519PrivateKey.generate()
    private = directory / (name + "-private.pem")
    private.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()))
    private.chmod(0o600)
    public = directory / (name + "-public.pem")
    public.write_bytes(key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    public.chmod(0o600)
    return private, public, signed.fingerprint(key.public_key())


@pytest.fixture
def case(tmp_path):
    if os.getuid() == 0:
        pytest.skip("operator acceptance requires non-root Linux")
    producer = tmp_path / "producer"
    producer.mkdir(mode=0o700)
    report = cross.produce(producer)
    archive = producer / "transfer" / "snapshot.zip"
    keys = tmp_path / "keys"
    keys.mkdir(mode=0o700)
    snapshot_private, snapshot_public, snapshot_pin = generate_signer(keys, "snapshot")
    checkpoint_private, checkpoint_public, checkpoint_pin = generate_signer(keys, "checkpoint")
    signature = keys / "snapshot-signature.json"
    signed.sign(archive, report["snapshot_sha256"], cross.WORKSPACE,
                report["workspace_sha256"], snapshot_private, snapshot_pin, signature)
    aes = keys / "aes.key"
    signed.write_private_new(aes, os.urandom(32))
    sealed = keys / "snapshot.sealed"
    enc_report = encrypted.encrypt(
        archive, report["snapshot_sha256"], cross.WORKSPACE,
        report["workspace_sha256"], signature, snapshot_public,
        snapshot_pin, aes, sealed)
    scratch = tmp_path / "scratch"
    scratch.mkdir(mode=0o700)
    root = tmp_path / "recovered"
    root.mkdir(mode=0o700)
    return {"sealed": sealed, "encrypted_sha": enc_report["encrypted_sha256"],
            "archive_sha": report["snapshot_sha256"],
            "workspace_sha": report["workspace_sha256"],
            "snapshot_signer": snapshot_pin,
            "checkpoint_signer": checkpoint_pin,
            "checkpoint_public": checkpoint_public,
            "checkpoint_private": checkpoint_private,
            "snapshot_public": snapshot_public,
            "snapshot_signature": signature, "aes": aes,
            "scratch": scratch, "root": root,
            "folder": keys, "workspace": cross.WORKSPACE}


def publish(c, sequence=0, predecessor=None, predecessor_sha=None, destination=None, **overrides):
    args = {**c, **overrides}
    if destination is None:
        destination = args["folder"] / ("checkpoint-" + str(sequence + 1) + ".json")
    return checkpoint.publish(
        args["workspace"], args["sealed"], args["encrypted_sha"],
        args["archive_sha"], args["workspace_sha"], args["snapshot_signer"],
        args["checkpoint_private"], args["checkpoint_public"],
        args["checkpoint_signer"], predecessor,
        predecessor_sha or checkpoint.ZERO, sequence, destination)


def verify(c, path, trusted_sha, sequence, **overrides):
    args = {**c, **overrides}
    return checkpoint.check(path, trusted_sha, sequence,
                            args["checkpoint_public"], args["checkpoint_signer"],
                            args["sealed"])


def recovery(c, path, trusted_sha, sequence, **overrides):
    a = {**c, **overrides}
    return checkpoint.recover(
        path, trusted_sha, sequence, a["checkpoint_public"],
        a["checkpoint_signer"], a["sealed"], a["aes"],
        a["snapshot_signature"], a["snapshot_public"],
        a["scratch"], a["root"])


def test_two_signed_checkpoints_and_recovery_pins_reject_older_head(case):
    one = publish(case)
    p1 = case["folder"] / "checkpoint-1.json"
    two = publish(case, sequence=1, predecessor=p1,
                  predecessor_sha=one["checkpoint_sha256"])
    p2 = case["folder"] / "checkpoint-2.json"
    assert one["sequence"] == 1
    assert two["sequence"] == 2
    assert checkpoint.read_checkpoint(p2, two["checkpoint_sha256"], 2,
                                      case["checkpoint_public"],
                                      case["checkpoint_signer"])["previous_sha256"] == one["checkpoint_sha256"]
    assert verify(case, p2, two["checkpoint_sha256"], 2)["status"] == \
        "checkpoint-matches-explicit-trusted-head"
    with pytest.raises(checkpoint.Denied, match="checkpoint-trusted-head-mismatch"):
        recovery(case, p1, two["checkpoint_sha256"], 2)
    assert not list(case["scratch"].iterdir()) and not list(case["root"].iterdir())
    with pytest.raises(checkpoint.Denied, match="checkpoint-trusted-sequence-or-signer-mismatch"):
        recovery(case, p1, one["checkpoint_sha256"], 2)
    assert not list(case["scratch"].iterdir()) and not list(case["root"].iterdir())
    result = recovery(case, p2, two["checkpoint_sha256"], 2)
    assert result["status"] == "explicit-trusted-checkpoint-offline-recovery"
    assert result["signed_and_authenticated_encryption_verified"] is True
    assert result["independent_latest_attested"] is False
    assert result["jobs_restarted"] is False
    assert not list(case["scratch"].iterdir())
    ws = cross.Workspace(case["root"], cross.WORKSPACE)
    assert ws.read("input.txt") == cross.INPUT
    assert ws.read("result.txt") == cross.OUTPUT
    journal = cross.ApprovalJournal(ws)
    record = journal.read(cross.DIGEST)
    with pytest.raises(cross.WorkspaceDenied):
        journal.claim(cross.DIGEST, version=3,
                      workspace_before=record["workspace_sha256_before"],
                      execution_nonce="d" * 32)


def test_checkpoint_signature_or_payload_tampering_denied_before_decrypt(case):
    one = publish(case)
    path = case["folder"] / "checkpoint-1.json"
    original = json.loads(path.read_text())
    edited = dict(original)
    edited["signature_hex"] = "0" * 128
    path.write_bytes(checkpoint.canonical(edited))
    new_digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(checkpoint.Denied, match="checkpoint-signature-invalid"):
        recovery(case, path, new_digest, 1)
    assert not list(case["scratch"].iterdir()) and not list(case["root"].iterdir())
    path.write_bytes(checkpoint.canonical(original))
    assert verify(case, path, one["checkpoint_sha256"], 1)["sequence"] == 1


def test_wrong_checkpoint_key_pin_rejected(case):
    one = publish(case)
    path = case["folder"] / "checkpoint-1.json"
    _, fake_pub, fake_pin = generate_signer(case["folder"], "untrusted")
    with pytest.raises(checkpoint.Denied, match="checkpoint-public-key-pin-mismatch"):
        verify(case, path, one["checkpoint_sha256"], 1,
               checkpoint_public=fake_pub)
    with pytest.raises(checkpoint.Denied, match="checkpoint-trusted-sequence-or-signer-mismatch"):
        verify(case, path, one["checkpoint_sha256"], 1,
               checkpoint_signer=fake_pin)
    assert not list(case["root"].iterdir())


def test_refuse_unpinned_genesis_or_unknown_predecessor(case):
    with pytest.raises(checkpoint.Denied, match="explicit-genesis-required"):
        publish(case, predecessor_sha="1" * 64)
    assert not (case["folder"] / "checkpoint-1.json").exists()
    with pytest.raises(checkpoint.Denied, match="exact-predecessor-required"):
        publish(case, sequence=1)
    assert not (case["folder"] / "checkpoint-2.json").exists()
    first = publish(case)
    with pytest.raises(checkpoint.Denied, match="checkpoint-trusted-head-mismatch"):
        publish(case, sequence=1,
                predecessor=case["folder"] / "checkpoint-1.json",
                predecessor_sha="f" * 64)
    assert first["checkpoint_sha256"] != checkpoint.ZERO
    assert not (case["folder"] / "checkpoint-2.json").exists()


def test_encrypted_snapshot_drift_disallowed_on_new_checkpoint(case):
    with pytest.raises(Exception, match="encrypted-envelope-sha256-mismatch"):
        publish(case, encrypted_sha="a" * 64)
    assert not (case["folder"] / "checkpoint-1.json").exists()
    one = publish(case)
    tampered = bytearray(case["sealed"].read_bytes())
    tampered[-1] ^= 1
    changed = case["folder"] / "bad.sealed"
    signed.write_private_new(changed, bytes(tampered))
    with pytest.raises(Exception, match="encrypted-envelope-sha256-mismatch"):
        recovery(case, case["folder"] / "checkpoint-1.json",
                 one["checkpoint_sha256"], 1, sealed=changed)
    assert not list(case["scratch"].iterdir()) and not list(case["root"].iterdir())


def test_wrong_aes_key_rejected_after_trusted_head_without_plaintext(case):
    first = publish(case)
    fake_key = case["folder"] / "wrong-aes.key"
    signed.write_private_new(fake_key, os.urandom(32))
    with pytest.raises(Exception, match="encrypted-authentication-failed"):
        recovery(case, case["folder"] / "checkpoint-1.json",
                 first["checkpoint_sha256"], 1, aes=fake_key)
    assert not list(case["scratch"].iterdir()) and not list(case["root"].iterdir())


def test_recovery_cannot_overwrite_existing_root(case):
    first = publish(case)
    keep = case["root"] / "untouched.txt"
    keep.write_text("keep user data")
    with pytest.raises(checkpoint.Denied, match="recovery-root-must-be-empty"):
        recovery(case, case["folder"] / "checkpoint-1.json",
                 first["checkpoint_sha256"], 1)
    assert keep.read_text() == "keep user data"
    assert not list(case["scratch"].iterdir())


def test_duplicate_json_keys_symlink_and_existing_checkpoint_denied(case):
    first = publish(case)
    original = case["folder"] / "checkpoint-1.json"
    with pytest.raises(FileExistsError):
        publish(case)
    alias = case["folder"] / "alias.json"
    alias.symlink_to(original)
    with pytest.raises(OSError):
        verify(case, alias, first["checkpoint_sha256"], 1)
    original.write_bytes(b'{"payload":{},"payload":{},"signature_hex":"' + b"0" * 128 + b'"}')
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    with pytest.raises(Exception, match="invalid-json"):
        verify(case, original, digest, 1)


def test_cli_requires_explicit_consent_and_exact_head(case, capsys):
    checkpoint_file = case["folder"] / "checkpoint-1.json"
    cp_args = ["--checkpoint", str(checkpoint_file),
               "--checkpoint-public-key", str(case["checkpoint_public"]),
               "--checkpoint-signer-sha256", case["checkpoint_signer"]]
    publish_args = ["publish", *cp_args,
                    "--checkpoint-private-key", str(case["checkpoint_private"]),
                    "--sealed", str(case["sealed"]),
                    "--workspace", case["workspace"],
                    "--encrypted-sha256", case["encrypted_sha"],
                    "--archive-sha256", case["archive_sha"],
                    "--workspace-sha256", case["workspace_sha"],
                    "--snapshot-signer-sha256", case["snapshot_signer"],
                    "--previous-sha256", checkpoint.ZERO,
                    "--previous-sequence", "0"]
    assert checkpoint.main(publish_args) == 2
    assert not checkpoint_file.exists()
    assert checkpoint.main(publish_args + ["--approve-publish"]) == 0
    trusted_head = hashlib.sha256(checkpoint_file.read_bytes()).hexdigest()
    recover_args = ["recover", *cp_args, "--sealed", str(case["sealed"]),
                    "--aes-key", str(case["aes"]),
                    "--snapshot-signature", str(case["snapshot_signature"]),
                    "--snapshot-public-key", str(case["snapshot_public"]),
                    "--scratch", str(case["scratch"]), "--root", str(case["root"])]
    assert checkpoint.main(recover_args + ["--approve-recover"]) == 2
    assert checkpoint.main(recover_args + ["--trusted-head-sha256", trusted_head,
                                           "--trusted-sequence", "1"]) == 2
    assert not list(case["root"].iterdir())
    assert checkpoint.main(["check", *cp_args, "--trusted-head-sha256", trusted_head,
                            "--trusted-sequence", "1", "--sealed", str(case["sealed"])]) == 0
    out = capsys.readouterr()
    assert case["workspace"] not in out.err
    assert "production_ready" in out.out
