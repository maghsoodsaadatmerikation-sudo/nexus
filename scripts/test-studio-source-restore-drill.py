#!/usr/bin/env python3
"""Synthetic privacy-safe negative tests for current-live Studio source restore."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).with_name("studio-source-restore-drill.py")
spec = importlib.util.spec_from_file_location("nexus_restore_drill", SCRIPT)
drill = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drill)


class SourceRestoreDrillTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="nexus-source-restore-synthetic-")
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.zip = self.base / "witness.zip"
        self.witness = self.base / "witness.json"
        self.dest = self.base / "restored-source"
        self.report = self.base / "drill.json"
        # Synthetic historical-inventory fixture, not actual historical bytes.
        current = drill.fallback.gate.source_assets()
        self.assets = {name: current[name] for name in drill.FILES}
        self.assertEqual(len(self.assets), 17)
        drill.fallback.archive(self.assets, self.zip)
        statuses = {name: "MATCH" for name in drill.FILES}
        doc = drill.fallback.make_report(
            self.assets, statuses, drill.digest(self.zip.read_bytes())
        )
        self.witness.write_text(json.dumps(doc))
        drill.fallback.verify(self.zip, self.witness)

    def build(self):
        return drill.restore(self.zip, self.witness, self.dest, self.report)

    def test_exact_fallback_bytes_restored_under_private_temporary_directory(self):
        output = self.build()
        self.assertEqual(output["schema"], drill.SCHEMA)
        self.assertEqual(output["source_commit"], drill.fallback.LIVE_COMMIT)
        self.assertEqual(output["restored_public_files"], 17)
        self.assertTrue(output["source_exact_bytes_reconstituted"])
        self.assertFalse(output["real_browser_tested_by_this_step"])
        self.assertFalse(output["actual_render_rollback_executed"])
        self.assertFalse(output["render_build_artifact_retained_confirmed"])
        self.assertEqual(output["authority"], "none")
        self.assertEqual(drill.verify_restored(self.dest, self.zip, self.witness)
                         ["source_assets"]["index.html"]["sha256"],
                         output["restored_html_sha256"])
        self.assertEqual(drill.restored_tree(self.dest), self.assets)
        self.assertEqual((self.dest / "public/studio/index.html").stat().st_mode & 0o777, 0o600)

    def test_edit_or_missing_pdf_worker_fails_restore_verification(self):
        self.build()
        worker = self.dest / "public/studio/pdf/pdf.worker.min.mjs"
        worker.write_bytes(b"synthetic-modified-pdf-module")
        with self.assertRaises(ValueError):
            drill.verify_restored(self.dest, self.zip, self.witness)
        worker.write_bytes(self.assets["pdf/pdf.worker.min.mjs"])
        worker.unlink()
        with self.assertRaises(ValueError):
            drill.verify_restored(self.dest, self.zip, self.witness)

    def test_extra_private_file_and_symlink_refused(self):
        self.build()
        secret = self.dest / "public/studio/private-user-archive.json"
        secret.write_text("synthetic fixture")
        with self.assertRaises(ValueError):
            drill.verify_restored(self.dest, self.zip, self.witness)
        secret.unlink()
        shortcut = self.dest / "public/studio/icons/alias.png"
        shortcut.symlink_to(self.dest / "public/studio/icons/nexus-192.png")
        with self.assertRaises(ValueError):
            drill.verify_restored(self.dest, self.zip, self.witness)

    def test_current_only_astronomy_asset_is_rejected_in_historical_restore(self):
        self.build()
        vendor = self.dest / "public/studio/vendor"
        vendor.mkdir()
        (vendor / "astronomy-2.1.19.min.js").write_bytes(b"synthetic extra asset")
        with self.assertRaises(ValueError):
            drill.verify_restored(self.dest, self.zip, self.witness)

    def test_existing_destination_and_output_are_never_overwritten(self):
        self.dest.mkdir()
        marker = self.dest / "user-content.txt"
        marker.write_text("never overwrite owner content")
        with self.assertRaises(ValueError):
            self.build()
        self.assertEqual(marker.read_text(), "never overwrite owner content")
        self.assertFalse(self.report.exists())
        self.dest.joinpath("user-content.txt").unlink()
        self.dest.rmdir()
        self.report.write_bytes(b"preserve-output")
        with self.assertRaises(ValueError):
            self.build()
        self.assertEqual(self.report.read_bytes(), b"preserve-output")
        self.assertFalse(self.dest.exists())

    def test_wrong_or_tampered_input_archive_rejected_before_creation(self):
        self.zip.write_bytes(b"not-zip")
        with self.assertRaises((ValueError, zipfile.BadZipFile)):
            self.build()
        self.assertFalse(self.dest.exists())
        self.assertFalse(self.report.exists())

    def test_untrusted_manifest_authority_blocks_source_restoration(self):
        doc = json.loads(self.witness.read_text())
        for key, value in (
            ("actual_rollback_executed", True),
            ("source_commit", "a"*40),
            ("rollback_render_build_artifact_confirmed", True),
            ("provider_metadata_rechecked_during_workflow", True),
        ):
            with self.subTest(key=key):
                forged = copy.deepcopy(doc)
                forged[key] = value
                self.witness.write_text(json.dumps(forged))
                with self.assertRaises(ValueError):
                    self.build()
                self.assertFalse(self.dest.exists())
        self.witness.write_text(json.dumps(doc))

    def test_unsupported_member_cannot_be_extracted(self):
        with zipfile.ZipFile(self.zip, "a") as dst:
            dst.writestr(drill.fallback.BUNDLE + "/../../PRIVATE-KEY", "synthetic")
        with self.assertRaises(ValueError):
            self.build()
        self.assertFalse(self.dest.exists())

    def test_workflow_runs_immutable_source_browser_in_disposable_local_tree(self):
        workflow = (SCRIPT.parent.parent / ".github/workflows/studio-live-source-fallback.yml").read_text()
        for name in (
            "studio-source-restore-drill.py",
            "test-studio-source-restore-drill.py",
            "test-studio-static-browser.mjs",
            "nexus-studio-restore-browser.json",
            "--verify",
            "source_exact_bytes_reconstituted",
        ):
            self.assertIn(name, workflow)
        self.assertIn("contents: read", workflow)
        self.assertNotIn("trigger_deploy", workflow)


if __name__ == "__main__":
    unittest.main(verbosity=2)
