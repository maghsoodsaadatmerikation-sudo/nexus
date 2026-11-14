#!/usr/bin/env python3
"""Adversarial test for explicitly enrolled empty synthetic volumes only."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("enroll-new-volume.py")
spec = importlib.util.spec_from_file_location("enroll_new_volume", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

ID = "1234567890abcdef1234567890abcdef"


class EnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nexus-volume-enrollment-test-")
        self.root = Path(self.tmp.name)
        self.target = self.root / "data"
        self.target.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def enroll(self, root=None, volume_id=ID, *, offline=True, confirm=module.ACK):
        return module.enroll(
            self.target if root is None else root,
            volume_id,
            offline=offline,
            confirmation=confirm,
        )

    def test_only_explicit_empty_volume_can_be_enrolled(self):
        self.enroll()
        marker = self.target / module.MARKER
        self.assertEqual(marker.read_bytes(), module.PREFIX + ID.encode() + b"\n")
        self.assertEqual(marker.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(ValueError):
            self.enroll()  # Never adopt/rewrite a previously enrolled volume.
        self.assertEqual(marker.read_bytes(), module.PREFIX + ID.encode() + b"\n")

    def test_nonempty_realistic_gateway_volume_refused(self):
        (self.target / "requests").mkdir()
        with self.assertRaises(ValueError):
            self.enroll()
        self.assertFalse((self.target / module.MARKER).exists())

    def test_missing_directory_and_aliases_refused(self):
        with self.assertRaises(OSError):
            self.enroll(self.root / "missing")
        alias = self.root / "alias"
        alias.symlink_to(self.target, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.enroll(alias)
        self.assertFalse((self.target / module.MARKER).exists())

    def test_wrong_id_and_explicit_confirmation_refused(self):
        for token in ["", "short", "A" * 32, "abc-" * 8, "g" * 32]:
            with self.subTest(token=token), self.assertRaises(ValueError):
                self.enroll(volume_id=token)
        with self.assertRaises(ValueError):
            self.enroll(offline=False)
        with self.assertRaises(ValueError):
            self.enroll(confirm="I AM MIGRATING AN EXISTING VOLUME")
        self.assertEqual(list(self.target.iterdir()), [])

    def test_cli_rejects_missing_confirmation_without_filesystem_side_effects(self):
        cmd = [sys.executable, str(SCRIPT), str(self.target), "--volume-id", ID,
               "--confirm", module.ACK]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(list(self.target.iterdir()), [])
        proc = subprocess.run(cmd + ["--offline"], capture_output=True, text=True, timeout=6)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn(ID, proc.stdout)
        self.assertTrue((self.target / module.MARKER).is_file())


if __name__ == "__main__":
    unittest.main()
