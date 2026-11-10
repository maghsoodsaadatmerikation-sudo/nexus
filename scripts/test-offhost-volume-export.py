#!/usr/bin/env python3
"""Fail-closed synthetic external-volume intake tests. No Railway access."""
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("verify-offhost-volume-export.py")
VOLUME = "cc47a350-6c7e-4487-89d9-c4b390f94884"
DEPLOY = "db2fd959-918e-49d5-b077-1ac74fac9a82"
COMMIT = "3c0977f4c7fc9fb5e9a78bdb1eeb581cb3cb4959"


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nexus-offhost-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.export = self.root / "downloaded"
        self.export.mkdir()
        (self.export / "requests").mkdir()
        (self.export / "77.json").write_text(json.dumps({
            "schema_version": 1, "workspace": {"id": "w"}, "events": []
        }))
        (self.export / "requests" / "6163636570746564").write_bytes(b"pending\n")
        self.out = self.root / "private-intake"

    def command(self, *options):
        return subprocess.run([sys.executable, str(SCRIPT),
            "--export-root", str(self.export),
            "--private-evidence-dir", str(self.out),
            "--volume-id", VOLUME, "--deployment-id", DEPLOY,
            "--runtime-commit", COMMIT, *options], text=True, capture_output=True)

    def test_copy_is_private_and_quarantined(self):
        result = self.command()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(stat.S_IMODE(self.out.stat().st_mode), 0o700)
        report = json.loads((self.out / "intake-report.json").read_text())
        self.assertEqual(report["status"], "STRUCTURAL_REHEARSAL_PASS")
        self.assertEqual(report["copy_provenance"], "unverified")
        self.assertEqual(report["independent_railway_backup"], "not_proven")
        self.assertEqual(report["live_recovery"], "not_evaluated")
        self.assertTrue(report["restored_quarantined"])
        self.assertEqual(report["file_count"], 2)
        self.assertTrue((self.out / "isolated-restore-rehearsal" /
                         ".nexus-recovery-required").exists())
        self.assertEqual((self.export / "requests" / "6163636570746564").read_bytes(),
                         b"pending\n")
        for secret in [str(self.export), "PRIVATE_SENTINEL", "accepted"]:
            self.assertNotIn(secret, result.stdout + result.stderr)
        self.assertNotEqual(self.command().returncode, 0)

    def test_invalid_data_is_blocked_without_success_evidence(self):
        (self.export / "77.json").write_text('{"private": "PRIVATE_SENTINEL"}')
        result = self.command()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("PRIVATE_SENTINEL", result.stdout + result.stderr)
        self.assertFalse((self.out / "intake-report.json").exists())

    def test_symlink_source_is_rejected(self):
        link = self.root / "linked"
        link.symlink_to(self.export, target_is_directory=True)
        self.export = link
        self.assertNotEqual(self.command().returncode, 0)
        self.assertFalse(self.out.exists())

    def test_unsafe_output_parent_is_rejected(self):
        self.out = self.export / "should-not-write-here"
        self.assertNotEqual(self.command().returncode, 0)
        self.assertFalse(self.out.exists())

    def test_bad_deployment_identity_is_rejected(self):
        result = self.command("--deployment-id", "invalid")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.out.exists())


if __name__ == "__main__":
    unittest.main()
