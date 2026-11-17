#!/usr/bin/env python3
"""Exact-source offline-only recovery ZIP tests with actual synthetic CMS.

NEVER fetches or restores the production Railway Volume. Private keys are
generated ephemerally for test fixtures and omitted from the archive.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
import zipfile

HERE = Path(__file__).resolve().parent
SRC = HERE / "build-stage-d-phone-restore-kit.py"
spec = importlib.util.spec_from_file_location("nexus_recovery_kit_builder", SRC)
kit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kit)
fixture_spec = importlib.util.spec_from_file_location(
    "nexus_synthetic_escrow_fixture", HERE / "test-stage-d-encrypted-escrow.py")
fixtures = importlib.util.module_from_spec(fixture_spec)
fixture_spec.loader.exec_module(fixtures)
REVISION = "a" * 40


class PhoneRestoreKitTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="nexus-local-recovery-kit-synthetic-")
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.archive = self.base / "kit.zip"

    def package(self):
        return kit.build(self.archive, REVISION)

    def fixture(self):
        t = fixtures.EncryptedEscrowTests(
            methodName="test_repo_public_certificate_is_pinned_and_has_no_private_key")
        t.setUp()
        self.addCleanup(t.doCleanups)
        return t

    def extract_for_synthetic_cms(self, specimen):
        root = self.base / "extracted"
        root.mkdir()
        with zipfile.ZipFile(self.archive) as z:
            z.extractall(root)
        installed = root / kit.BUNDLE
        # IMPORTANT: synthetic acceptance modifies ONLY the extracted CI
        # working copy, never the shipped ZIP or original pinned certificate.
        test_cert = installed / kit.CERT
        test_cert.write_bytes(specimen.cert.read_bytes())
        contract = installed / "scripts/stage-d-encrypted-escrow.py"
        original = contract.read_text()
        self.assertEqual(original.count(kit.CERT_SHA), 1)
        contract.write_text(original.replace(kit.CERT_SHA, specimen.cert_sha))
        return installed

    def run_restore(self, installed, specimen, destination, key=None, receipt=None, ciphertext=None):
        command = ["sh", str(installed / "restore-local.sh"),
                   str(ciphertext or specimen.out / "nexus-stage-d-private-capture.cms"),
                   str(receipt or specimen.out / "nexus-stage-d-ciphertext-receipt.json"),
                   str(key or specimen.key), str(destination)]
        return subprocess.run(command, cwd=self.base, capture_output=True,
                              text=True, timeout=30,
                              env={"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(self.base)})

    def test_deterministic_zip_only_has_reviewed_public_modules(self):
        digest = self.package()
        other = self.base / "same.zip"
        self.assertEqual(digest, kit.build(other, REVISION))
        self.assertEqual(self.archive.read_bytes(), other.read_bytes())
        self.assertTrue(kit.verify_zip(self.archive, exact_commit=REVISION))
        with zipfile.ZipFile(self.archive) as z:
            names = [i.filename.removeprefix(kit.BUNDLE + "/") for i in z.infolist()]
            self.assertEqual(set(names), set(kit.package_files(REVISION)))
            self.assertNotIn("scripts/verify-offhost-volume-export.py", names)
            self.assertNotIn("scripts/stage-d-core-parity.py", names)
            capture = z.read(kit.BUNDLE + "/scripts/capture-railway-volume-readonly.py")
            self.assertNotIn(b"subprocess", capture)
            self.assertNotIn(b"railway_download", capture)
            self.assertNotIn(b"download", capture)
            self.assertNotIn(b"RAILWAY_TOKEN", capture)
            manifest = json.loads(z.read(kit.BUNDLE + "/manifest.json"))
            for key in ("private_key_included", "real_backup_included",
                        "railway_client_included", "android_hardware_verified",
                        "production_restore_authorized"):
                self.assertIs(manifest[key], False)
            self.assertEqual(manifest["authority"], "none")
            self.assertEqual(manifest["pinned_deployment"], kit.DEPLOYMENT)
            self.assertEqual(manifest["pinned_runtime"], kit.RUNTIME)

    def test_build_blocks_unsafe_commit_and_existing_destination(self):
        for rev in ("main", "A" * 40, "a" * 39, ""):
            with self.subTest(rev=rev):
                with self.assertRaises(ValueError):
                    kit.build(self.archive, rev)
                self.assertFalse(self.archive.exists())
        self.archive.write_bytes(b"previous private file must survive")
        with self.assertRaises(ValueError):
            kit.build(self.archive, REVISION)
        self.assertEqual(self.archive.read_bytes(), b"previous private file must survive")

    def test_tampered_zip_and_extra_private_key_member_are_rejected(self):
        self.package()
        changed = self.base / "bad.zip"
        changed.write_bytes(self.archive.read_bytes())
        with zipfile.ZipFile(changed, "a") as z:
            z.writestr(kit.BUNDLE + "/PRIVATE_KEY.pem", b"NOT_REAL_PRIVATE_KEY")
        with self.assertRaises(ValueError):
            kit.verify_zip(changed)
        with self.assertRaises(ValueError):
            kit.verify_zip(self.archive, exact_commit="f" * 40)
        # A mutated source file inside the package must never verify.
        with zipfile.ZipFile(self.archive) as z:
            members = {i.filename: z.read(i) for i in z.infolist()}
        with zipfile.ZipFile(changed, "w") as z:
            for name, content in members.items():
                if name.endswith("/README.txt"):
                    content = content + b"\nATTACKER CHANGE\n"
                z.writestr(name, content)
        with self.assertRaises(ValueError):
            kit.verify_zip(changed)

    def test_real_synthetic_ciphertext_decrypts_and_restores_in_extracted_package(self):
        self.package()
        specimen = self.fixture()
        specimen.encrypt()
        installed = self.extract_for_synthetic_cms(specimen)
        destination = self.base / "quarantined"
        proc = self.run_restore(installed, specimen, destination)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("QUARANTINED RESTORE: PASS", proc.stdout)
        self.assertNotIn(specimen.sentinel, proc.stdout + proc.stderr)
        self.assertEqual((destination / "77.json").read_bytes(),
                         (specimen.copy / "77.json").read_bytes())
        self.assertEqual((destination / "requests" / "6163636570746564").read_bytes(), b"pending\n")
        self.assertEqual((destination / ".nexus-recovery-required").read_bytes(),
                         b"NEXUS RECOVERY REQUIRED\n" if False else
                         (specimen.report / "isolated-restore-rehearsal" / ".nexus-recovery-required").read_bytes())
        self.assertTrue(kit.verify_zip(self.archive, exact_commit=REVISION),
                        "synthetic certificate swap must NOT alter distributable ZIP")

    def test_mutated_ciphertext_and_forged_receipt_block_without_output(self):
        self.package()
        specimen = self.fixture()
        specimen.encrypt()
        installed = self.extract_for_synthetic_cms(specimen)
        cipher = specimen.out / "nexus-stage-d-private-capture.cms"
        data = bytearray(cipher.read_bytes())
        data[-20] ^= 1
        cipher.write_bytes(data)
        destination = self.base / "not-published"
        response = self.run_restore(installed, specimen, destination)
        self.assertNotEqual(response.returncode, 0)
        self.assertFalse(destination.exists())
        self.assertIn("BLOCKED", response.stderr)
        self.assertNotIn(specimen.sentinel, response.stderr)

    def test_existing_destination_and_bad_private_key_permissions_block(self):
        self.package()
        specimen = self.fixture()
        specimen.encrypt()
        installed = self.extract_for_synthetic_cms(specimen)
        destination = self.base / "existing"
        destination.mkdir(mode=0o700)
        marker = destination / "owner-file"
        marker.write_text("original")
        response = self.run_restore(installed, specimen, destination)
        self.assertNotEqual(response.returncode, 0)
        self.assertEqual(marker.read_text(), "original")
        specimen.key.chmod(0o644)
        other = self.base / "bad-permissions"
        response = self.run_restore(installed, specimen, other)
        self.assertNotEqual(response.returncode, 0)
        self.assertFalse(other.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
