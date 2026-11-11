#!/usr/bin/env python3
"""Fully synthetic authenticated escrow -> offline quarantined recovery tests.

No Railway credentials, provider traffic, user files or actual production copy.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

DIR = Path(__file__).resolve().parent

def load(path, alias):
    spec = importlib.util.spec_from_file_location(alias, DIR / path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

recovery = load("restore-stage-d-encrypted-escrow.py", "stage_d_offline_recovery_tests")
old = load("test-stage-d-encrypted-escrow.py", "stage_d_escrow_test_fixtures")


class OfflineRecoveryTests(unittest.TestCase):
    def setUp(self):
        fixture = old.EncryptedEscrowTests(
            methodName="test_repo_public_certificate_is_pinned_and_has_no_private_key")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.f = fixture
        self.target = fixture.base / "quarantined-restored-private-data"
        self.ciphertext, self.receipt = fixture.encrypt()
        self.meta = fixture.out / "nexus-stage-d-ciphertext-receipt.json"

    def recover(self, key=None, destination=None):
        with patch.object(recovery.escrow, "CERT", self.f.cert), \
             patch.object(recovery.escrow, "CERT_SHA256", self.f.cert_sha), \
             contextlib.redirect_stdout(io.StringIO()) as console:
            recovery.recover(self.ciphertext, self.meta,
                             key or self.f.key, destination or self.target)
            self.assertNotIn(self.f.sentinel, console.getvalue())
            self.assertIn("QUARANTINED RESTORE: PASS", console.getvalue())

    def refused(self, key=None, dest=None):
        with patch.object(recovery.escrow, "CERT", self.f.cert), \
             patch.object(recovery.escrow, "CERT_SHA256", self.f.cert_sha):
            with self.assertRaises((ValueError, OSError, subprocess.SubprocessError,
                                    tarfile.TarError)):
                recovery.recover(self.ciphertext, self.meta,
                                 key or self.f.key, dest or self.target)
        self.assertFalse(self.target.exists())

    def rewrite_meta(self, field, value):
        data = json.loads(self.meta.read_text())
        data[field] = value
        self.meta.write_text(json.dumps(data))

    def reencrypt_tar(self, mapping):
        raw = io.BytesIO()
        with tarfile.open(fileobj=raw, mode="w") as t:
            for name, body in mapping:
                member = tarfile.TarInfo(name)
                member.mode = 0o600
                member.size = len(body)
                t.addfile(member, io.BytesIO(body))
        cmd = ["openssl", "cms", "-encrypt", "-aes-256-gcm",
               "-binary", "-stream", "-outform", "DER", str(self.f.cert)]
        r = subprocess.run(cmd, input=raw.getvalue(),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=15, check=True)
        self.ciphertext.write_bytes(r.stdout)
        self.rewrite_meta("ciphertext_sha256", hashlib.sha256(r.stdout).hexdigest())
        self.rewrite_meta("ciphertext_bytes", len(r.stdout))

    def evidence_map(self):
        result = self.f.decrypt(self.ciphertext)
        self.assertEqual(result.returncode, 0)
        with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:") as t:
            return {i.name: t.extractfile(i).read() for i in t}

    def test_full_aes_gcm_escrow_roundtrip_to_private_quarantined_copy(self):
        self.recover()
        self.assertEqual((self.target / "77.json").read_bytes(),
                         (self.f.copy / "77.json").read_bytes())
        self.assertEqual((self.target / "requests" / "6163636570746564").read_bytes(),
                         b"pending\n")
        self.assertEqual((self.target / ".nexus-recovery-required").read_bytes(),
                         recovery.snapshot.RECOVERY_BYTES)
        self.assertEqual({x.name for x in self.target.iterdir()},
                         {"77.json", "requests", ".nexus-recovery-required"})
        self.assertFalse((self.target / "nexus-private-data-snapshot.json").exists())
        self.assertFalse((self.target / "intake-report.json").exists())
        self.assertEqual(self.meta.stat().st_size > 0, True)

    def test_changed_ciphertext_without_digest_update_is_rejected(self):
        data = bytearray(self.ciphertext.read_bytes())
        data[-24] ^= 0x20
        self.ciphertext.write_bytes(data)
        self.refused()

    def test_changed_ciphertext_with_forged_new_digest_fails_aes_gcm(self):
        data = bytearray(self.ciphertext.read_bytes())
        data[-24] ^= 0x20
        self.ciphertext.write_bytes(data)
        self.rewrite_meta("ciphertext_sha256", hashlib.sha256(data).hexdigest())
        self.refused()

    def test_wrong_private_key_cannot_decrypt(self):
        otherkey = self.f.base / "other-private-key.pem"
        cert = self.f.base / "other-private-cert.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048",
                        "-nodes", "-sha256", "-days", "1",
                        "-keyout", str(otherkey), "-out", str(cert),
                        "-subj", "/CN=Incorrect Recipient"],
                       check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=20)
        self.refused(key=otherkey)

    def test_unsafe_private_key_permissions_rejected_before_decrypt(self):
        self.f.key.chmod(0o644)
        self.refused()

    def test_key_symlink_is_not_followed(self):
        alias = self.f.base / "linked-key.pem"
        alias.symlink_to(self.f.key)
        self.refused(key=alias)

    def test_bad_external_receipt_claim_or_key_is_blocked(self):
        for key, value in (("seal", True), ("release_authorized", True),
                           ("authority", "production"),
                           ("independent_live_restore", "verified"),
                           ("status", "ATOMIC_BACKUP_PASS")):
            with self.subTest(key=key):
                self.rewrite_meta(key, value)
                self.refused()
                self.rewrite_meta(key, self.receipt[key])

    def test_duplicate_external_receipt_key_is_rejected(self):
        raw = self.meta.read_text()
        self.meta.write_text(raw[:-2] + ',"seal":true}')
        self.refused()

    def test_foreign_tar_member_rejected_without_extracting_anything(self):
        data = self.evidence_map()
        self.reencrypt_tar(list(data.items()) + [("../../outside.json", b"SECRET")])
        self.refused()
        self.assertFalse((self.f.base / "outside.json").exists())

    def test_duplicate_inner_tar_member_rejected_even_with_valid_gcm(self):
        data = self.evidence_map()
        members = list(data.items())
        self.reencrypt_tar(members + [members[0]])
        self.refused()

    def test_forged_internal_capture_receipt_is_rejected(self):
        files = self.evidence_map()
        internal = json.loads(files["capture-receipt.json"])
        internal["seal"] = True
        files["capture-receipt.json"] = json.dumps(internal).encode()
        self.reencrypt_tar(list(files.items()))
        self.refused()

    def test_forged_internal_snapshot_digest_is_rejected(self):
        files = self.evidence_map()
        internal = json.loads(files["intake-report.json"])
        internal["snapshot_sha256"] = "0" * 64
        files["intake-report.json"] = json.dumps(internal).encode()
        self.reencrypt_tar(list(files.items()))
        self.refused()

    def test_existing_target_never_overwritten(self):
        self.target.mkdir(mode=0o700)
        private = self.target / "must-survive"
        private.write_bytes(b"operator-original-unchanged")
        with patch.object(recovery.escrow, "CERT", self.f.cert), \
             patch.object(recovery.escrow, "CERT_SHA256", self.f.cert_sha):
            with self.assertRaises(recovery.RecoveryBlocked):
                recovery.recover(self.ciphertext, self.meta, self.f.key, self.target)
        self.assertEqual(private.read_bytes(), b"operator-original-unchanged")

    def test_helper_subprocess_does_not_inherit_provider_tokens(self):
        real = subprocess.run
        seen = []
        secrets = {"RAILWAY_TOKEN": "synthetic-provider-secret",
                   "RAILWAY_API_TOKEN": "synthetic-api-secret",
                   "GITHUB_TOKEN": "synthetic-git-secret",
                   "NEXUS_API_TOKEN": "synthetic-app-secret",
                   "PYTHONPATH": "/private/test"}
        def spy(args, **kwargs):
            if args[:3] == ["openssl", "cms", "-decrypt"]:
                env = kwargs["env"]
                self.assertFalse(set(secrets) & set(env))
                self.assertEqual(kwargs["stderr"], subprocess.DEVNULL)
                seen.append(True)
            return real(args, **kwargs)
        with patch.dict(os.environ, secrets), \
             patch.object(recovery.subprocess, "run", side_effect=spy):
            self.recover()
        self.assertEqual(seen, [True])

    def test_cli_failure_does_not_echo_private_data_paths_or_key(self):
        self.rewrite_meta("ciphertext_sha256", "0" * 64)
        stderr = io.StringIO()
        with patch.object(recovery.sys, "argv", [
            "restore-stage-d-encrypted-escrow.py",
            "--ciphertext", str(self.ciphertext),
            "--receipt", str(self.meta),
            "--private-key", str(self.f.key),
            "--destination", str(self.target)]), \
            patch.object(recovery.escrow, "CERT", self.f.cert), \
            patch.object(recovery.escrow, "CERT_SHA256", self.f.cert_sha), \
            contextlib.redirect_stderr(stderr):
            result = recovery.main()
        self.assertNotEqual(result, 0)
        self.assertFalse(self.target.exists())
        for secret in (str(self.f.base), str(self.f.key), self.f.sentinel):
            self.assertNotIn(secret, stderr.getvalue())

if __name__ == "__main__":
    unittest.main(verbosity=2)
