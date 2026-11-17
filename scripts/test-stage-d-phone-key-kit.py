#!/usr/bin/env python3
"""Tests reproducible public-only phone key kit; all RSA test keys synthetic.

No production private key, Railway token or real encrypted CMS backup.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).with_name("build-stage-d-phone-key-kit.py")
spec = importlib.util.spec_from_file_location("owner_key_kit", SCRIPT)
kit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kit)

COMMIT = "f" * 40


class PhoneKeyKitTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="nexus-phone-key-kit-synthetic-")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.archive = self.folder / "phone-kit.zip"

    def build(self):
        return kit.build(self.archive, COMMIT)

    def test_deterministic_two_independent_builds_and_bounded_contents(self):
        digest = self.build()
        other = self.folder / "other.zip"
        self.assertEqual(digest, kit.build(other, COMMIT))
        self.assertEqual(self.archive.read_bytes(), other.read_bytes())
        self.assertTrue(kit.verify(self.archive, expected_commit=COMMIT))
        with zipfile.ZipFile(self.archive) as z:
            files = {v.filename for v in z.infolist()}
            self.assertEqual(files, {kit.BUNDLE_ROOT + "/" + p for p in
                 (kit.CERT, kit.VERIFIER, "README.txt", "run-keycheck.sh", "manifest.json")})
            manifest = json.loads(z.read(kit.BUNDLE_ROOT + "/manifest.json"))
            self.assertEqual(manifest["source_commit"], COMMIT)
            self.assertEqual(manifest["pinned_recipient_cert_sha256"], kit.CERT_SHA256)
            self.assertFalse(manifest["private_key_included"])
            self.assertFalse(manifest["runtime_railway_access"])
            self.assertFalse(manifest["live_backup_included"])
            self.assertFalse(manifest["actual_android_verified"])
            launcher = z.read(kit.BUNDLE_ROOT + "/run-keycheck.sh").decode()
            self.assertNotIn("curl ", launcher)
            self.assertNotIn("wget ", launcher)
            self.assertNotIn("RAILWAY_TOKEN", launcher)
            self.assertIn("umask 077", launcher)
            self.assertEqual(hashlib.sha256(
                z.read(kit.BUNDLE_ROOT + "/" + kit.CERT)).hexdigest(),
                kit.CERT_SHA256)

    def test_bad_source_commit_is_refused_without_creating_file(self):
        for source in ("", "main", "a" * 39, "Z" * 40, "a" * 41):
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    kit.build(self.archive, source)
                self.assertFalse(self.archive.exists())

    def test_existing_destination_does_not_get_overwritten(self):
        self.archive.write_bytes(b"owner-data-sentinel")
        with self.assertRaises(ValueError):
            kit.build(self.archive, COMMIT)
        self.assertEqual(self.archive.read_bytes(), b"owner-data-sentinel")

    def test_modify_public_payload_without_updating_manifest_is_refused(self):
        self.build()
        with zipfile.ZipFile(self.archive) as orig:
            original = {i.filename: orig.read(i) for i in orig.infolist()}
        altered = self.folder / "modified.zip"
        with zipfile.ZipFile(altered, "w") as dest:
            for name, data in original.items():
                if name.endswith("/README.txt"):
                    data += b"\nUNREVIEWED EXTRA\n"
                dest.writestr(name, data)
        with self.assertRaises(ValueError):
            kit.verify(altered, expected_commit=COMMIT)

    def test_archive_extra_member_and_traversal_refused(self):
        self.build()
        for suffix in ("private-key.pem", "../../private-key.pem"):
            target = self.folder / ("bad-" + hashlib.sha256(suffix.encode()).hexdigest()[:8] + ".zip")
            target.write_bytes(self.archive.read_bytes())
            with zipfile.ZipFile(target, "a") as z:
                z.writestr(kit.BUNDLE_ROOT + "/" + suffix, b"NOT_REAL_KEY")
            with self.assertRaises(ValueError):
                kit.verify(target)

    def test_wrong_expected_commit_blocks_verification(self):
        self.build()
        with self.assertRaises(ValueError):
            kit.verify(self.archive, expected_commit="a" * 40)

    def test_packaged_verifier_decrypts_fresh_synthetic_rsa_cms(self):
        """Test real OpenSSL in extracted bundle using ONLY ephemeral test keys."""
        self.build()
        extracted = self.folder / "extract"
        extracted.mkdir()
        with zipfile.ZipFile(self.archive) as z:
            z.extractall(extracted)
        root = extracted / kit.BUNDLE_ROOT
        verifier = root / kit.VERIFIER
        self.assertTrue(verifier.is_file())
        p = importlib.util.spec_from_file_location("nexus_kit_synthetic_keycheck", verifier)
        module = importlib.util.module_from_spec(p)
        p.loader.exec_module(module)
        keys = self.folder / "synthetic-keys"
        keys.mkdir(mode=0o700)
        cert = keys / "synthetic-public.pem"
        private = keys / "synthetic-private.pem"
        wrong_cert = keys / "other-public.pem"
        wrong_private = keys / "other-private.pem"
        for key, pub in ((private, cert), (wrong_private, wrong_cert)):
            res = subprocess.run([
                str(module.OPENSSL), "req", "-x509", "-newkey", "rsa:2048",
                "-nodes", "-sha256", "-days", "1", "-keyout", str(key),
                "-out", str(pub), "-subj", "/CN=NEXUS synthetic fixture ONLY/"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            self.assertEqual(res.returncode, 0)
            key.chmod(0o600)
        digest = hashlib.sha256(cert.read_bytes()).hexdigest()
        self.assertTrue(module.prove(private, cert=cert, pinned_digest=digest, repo=root))
        with self.assertRaises(module.KeyCheckBlocked):
            module.prove(wrong_private, cert=cert, pinned_digest=digest, repo=root)
        private.chmod(0o644)
        with self.assertRaises(module.KeyCheckBlocked):
            module.prove(private, cert=cert, pinned_digest=digest, repo=root)

    def test_cli_verify_never_claims_private_custody(self):
        self.build()
        r = subprocess.run(["python3", str(SCRIPT), "--verify-zip", str(self.archive),
                             "--source-commit", COMMIT],
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("not independent signature", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
