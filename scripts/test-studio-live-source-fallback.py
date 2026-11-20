#!/usr/bin/env python3
"""Read-only prior-live source fallback ZIP tests: all network is synthetic."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SOURCE = Path(__file__).with_name("studio-live-source-fallback.py")
spec = importlib.util.spec_from_file_location("live_static_fallback", SOURCE)
fallback = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fallback)


class SourceFallbackTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="nexus-studio-fallback-synthetic-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.zip_path = self.root / "old-live-source.zip"
        self.report_path = self.root / "old-live-public-witness.json"
        assets = fallback.gate.source_assets()
        self.assets = {name: assets[name] for name in fallback.LEGACY_FILES}
        self.fetch = lambda name: self.assets[name]

    def build(self, fetch=None):
        # No network/old checkout is involved in unit tests. Real CI must
        # independently checkout the exact historical commit, call the CLI
        # against real Render HTTPS and disallow overriding fetch.
        with patch.object(fallback, "check_old_root", return_value=self.assets):
            return fallback.build(self.root, self.zip_path,
                                  self.report_path, fetch=fetch or self.fetch)

    def test_deterministic_private_free_source_fallback_bundle(self):
        report = self.build()
        self.assertEqual(report, fallback.verify(self.zip_path, self.report_path))
        self.assertTrue(report["origin_matches_pinned_live_source"])
        self.assertEqual(report["source_commit"], fallback.LIVE_COMMIT)
        self.assertEqual(report["current_live_deploy_at_snapshot"], fallback.LIVE_DEPLOY)
        for field in ("rollback_render_build_artifact_confirmed",
                      "rollback_action_available_in_connector",
                      "actual_rollback_executed", "production_deploy_executed",
                      "real_user_archive_recovered"):
            self.assertIs(report[field], False)
        self.assertEqual(report["authority"], "none")
        self.assertEqual(report["data_included"], "public_static_source_only")
        with zipfile.ZipFile(self.zip_path) as zipped:
            self.assertEqual(zipped.namelist(), sorted(
                fallback.BUNDLE+"/"+name for name in fallback.LEGACY_FILES))
        one = self.zip_path.read_bytes()
        self.zip_path.unlink()
        self.report_path.unlink()
        self.assertEqual(self.build()["archive_sha256"], fallback.sha(one))
        self.assertEqual(self.zip_path.read_bytes(), one)

    def test_live_source_mismatch_refuses_to_publish_fallback(self):
        def corrupt(name):
            return b"PUBLIC_CODE_HAS_CHANGED" if name == "index.html" else self.assets[name]
        with self.assertRaises(ValueError):
            self.build(fetch=corrupt)
        self.assertFalse(self.zip_path.exists())
        self.assertFalse(self.report_path.exists())
        def unreachable(name):
            if name == "service-worker.js":
                raise TimeoutError("synthetic-network-failure")
            return self.assets[name]
        with self.assertRaises(ValueError):
            self.build(fetch=unreachable)
        self.assertFalse(self.zip_path.exists())
        self.assertFalse(self.report_path.exists())

    def test_existing_output_is_never_overwritten(self):
        self.zip_path.write_bytes(b"owner-previous-file")
        with self.assertRaises(ValueError):
            self.build()
        self.assertEqual(self.zip_path.read_bytes(), b"owner-previous-file")
        self.assertFalse(self.report_path.exists())

    def test_asset_tampering_and_extra_file_are_blocked(self):
        self.build()
        with zipfile.ZipFile(self.zip_path) as zipped:
            original = {info.filename: zipped.read(info) for info in zipped.infolist()}
        mutated = self.root / "mutated.zip"
        with zipfile.ZipFile(mutated, "w") as zipped:
            for name, data in original.items():
                zipped.writestr(name, data)
            zipped.writestr(fallback.BUNDLE+"/private.pem", b"synthetic fake private")
        with self.assertRaises(ValueError):
            fallback.verify(mutated, self.report_path)
        with zipfile.ZipFile(mutated, "w") as zipped:
            for name, data in original.items():
                if name.endswith("/index.html"):
                    data += b"UNREVIEWED_HTML"
                zipped.writestr(name, data)
        with self.assertRaises(ValueError):
            fallback.verify(mutated, self.report_path)

    def test_forged_public_evidence_or_restoration_flags_refuse(self):
        self.build()
        import json
        baseline = json.loads(self.report_path.read_bytes())
        for key, value in (
            ("origin_matches_pinned_live_source", False),
            ("actual_rollback_executed", True),
            ("production_deploy_executed", True),
            ("rollback_render_build_artifact_confirmed", True),
            ("source_commit", "f"*40),
            ("live_service_id_at_snapshot", "srv-wrong-service"),
            ("render_workspace_id_at_snapshot", "tea-wrong-workspace"),
            ("current_live_deploy_at_snapshot", "dep-obsolete-live"),
            ("rollback_action_available_in_connector", True),
            ("real_user_archive_recovered", True),
            ("no_new_service_or_cost", False),
            ("data_included", "source_plus_private"),
            ("archive_sha256", "0"*64),
        ):
            with self.subTest(key=key):
                changed = copy.deepcopy(baseline)
                changed[key] = value
                self.report_path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):
                    fallback.verify(self.zip_path, self.report_path)
        self.report_path.write_text(json.dumps(baseline))
        self.assertEqual(fallback.verify(self.zip_path, self.report_path)["authority"], "none")

    def test_report_requires_all_nine_public_exact_matches(self):
        good={name:"MATCH" for name in fallback.gate.OBSERVE}
        report = fallback.make_report(self.assets, good, "a"*64)
        self.assertTrue(report["origin_matches_pinned_live_source"])
        with self.assertRaises(ValueError):
            fallback.make_report(self.assets, {**good, "index.html":"DRIFT"}, "a"*64)
        icons={**good, "icons/nexus-192.png": "PIXEL_MATCH",
               "icons/nexus-512.png": "PIXEL_MATCH"}
        report=fallback.make_report(self.assets, icons, "a"*64)
        self.assertTrue(report["origin_matches_pinned_live_source"])
        self.assertTrue(report["png_icons_compared_by_rgba_pixels"])
        with self.assertRaises(ValueError):
            fallback.make_report(self.assets, {**good, "service-worker.js": "PIXEL_MATCH"}, "a"*64)
        with self.assertRaises(ValueError):
            fallback.make_report(self.assets, {"index.html":"MATCH"}, "a"*64)
        with self.assertRaises(ValueError):
            fallback.make_report(self.assets, good, "UNPINNED")

    def test_public_only_allowlist(self):
        self.assertEqual(len(fallback.LEGACY_FILES), 13)
        self.assertEqual(len(fallback.gate.OBSERVE), 9)
        self.assertEqual(fallback.SERVICE, "srv-dbrjurc9v7es73cqe0v0")
        self.assertEqual(fallback.LIVE_COMMIT, "9e05b840fc2d36d7bc268aede2693ab4d6fb08e3")
        self.assertEqual(fallback.LIVE_DEPLOY, "dep-dbvkuonf3r2c73cj3930")


if __name__ == "__main__":
    unittest.main(verbosity=2)
