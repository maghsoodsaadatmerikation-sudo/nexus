#!/usr/bin/env python3
"""No-provider local cryptographic key-possession regression tests."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import hashlib

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("key_check", HERE / "verify-stage-d-recovery-key.py")
keycheck = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(keycheck)


class KeyProofTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nexus-key-proof-synthetic-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cert = self.root / "test-cert.pem"
        self.key = self.root / "test-key.pem"
        self.other = self.root / "other-key.pem"
        self.othercert = self.root / "other-cert.pem"
        for key, cert in ((self.key, self.cert), (self.other, self.othercert)):
            result = subprocess.run(
                [str(keycheck.OPENSSL), "req", "-x509", "-newkey", "rsa:2048",
                 "-nodes", "-sha256", "-days", "1", "-keyout", str(key),
                 "-out", str(cert), "-subj", "/CN=NEXUS synthetic only/"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=20, check=False)
            self.assertEqual(result.returncode, 0)
            key.chmod(0o600)
        self.digest = hashlib.sha256(self.cert.read_bytes()).hexdigest()

    def check(self, key=None, cert=None, digest=None):
        return keycheck.prove(key or self.key, cert or self.cert,
                              digest or self.digest, repo=HERE.parent)

    def test_correct_key_decrypts_fresh_challenge(self):
        self.assertTrue(self.check())

    def test_wrong_private_key_fails(self):
        with self.assertRaises(keycheck.KeyCheckBlocked):
            self.check(self.other)

    def test_unpinned_cert_fails_before_decrypt(self):
        with self.assertRaises(keycheck.KeyCheckBlocked):
            self.check(cert=self.othercert)

    def test_readable_by_other_users_is_refused(self):
        self.key.chmod(0o644)
        with self.assertRaises(keycheck.KeyCheckBlocked):
            self.check()

    def test_symlinked_private_key_fails(self):
        link = self.root / "linked-key.pem"
        link.symlink_to(self.key)
        with self.assertRaises(keycheck.KeyCheckBlocked):
            self.check(link)

    def test_hardlinked_private_key_fails(self):
        linked = self.root / "hardlink-key.pem"
        os.link(self.key, linked)
        with self.assertRaises(keycheck.KeyCheckBlocked):
            self.check()

    def test_nonabsolute_key_fails(self):
        with self.assertRaises(keycheck.KeyCheckBlocked):
            self.check(Path("relative.pem"))

    def test_public_cert_is_not_private_key(self):
        self.cert.chmod(0o600)
        with self.assertRaises(keycheck.KeyCheckBlocked):
            self.check(self.cert)

    def test_ci_is_explicitly_denied_without_reading_key(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
            with patch.object(sys, "argv", ["verify-stage-d-recovery-key.py", "--private-key", "/no-such-file"]):
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    self.assertEqual(keycheck.main(), 1)
                    self.assertIn("cloud runner prohibited", err.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
