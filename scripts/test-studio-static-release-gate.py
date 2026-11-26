#!/usr/bin/env python3
"""Fail-closed, public-code-only Studio release candidate unit tests."""
import importlib.util
import json
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("nexus_studio_release", HERE / "studio-static-release-gate.py")
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)
COMMIT = "c" * 40


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        fixture = tempfile.TemporaryDirectory(prefix="nexus-public-studio-release-synthetic-")
        self.addCleanup(fixture.cleanup)
        self.directory = Path(fixture.name)
        self.archive = self.directory / "candidate.zip"
        self.manifest_file = self.directory / "candidate.json"

    def build(self):
        return gate.build(self.archive, self.manifest_file, COMMIT)

    def test_exact_public_files_and_reproducible_zip(self):
        manifest = self.build()
        self.assertEqual(manifest, gate.verify(self.archive, self.manifest_file, COMMIT))
        second_archive = self.directory / "candidate2.zip"
        second_manifest = self.directory / "candidate2.json"
        gate.build(second_archive, second_manifest, COMMIT)
        self.assertEqual(self.archive.read_bytes(), second_archive.read_bytes())
        self.assertEqual(self.manifest_file.read_bytes(), second_manifest.read_bytes())
        self.assertEqual(manifest["schema"], gate.SCHEMA)
        self.assertEqual(manifest["source_commit"], COMMIT)
        self.assertEqual(manifest["content_count"], 19)
        self.assertEqual(manifest["readiness"], "REVIEW_CANDIDATE_ONLY")
        for name in ("contains_private_data", "contains_provider_secrets",
                     "production_promotion_authorized", "render_deploy_performed",
                     "android_hardware_tested"):
            self.assertIs(manifest[name], False)
        self.assertEqual(manifest["authority"], "none")
        with zipfile.ZipFile(self.archive) as zipped:
            members = zipped.namelist()
            self.assertEqual(len(members), 19)
            self.assertEqual(
                set(members), {gate.BUNDLE + "/" + name for name in gate.FILES})
            self.assertIn(gate.BUNDLE + "/studio-orchestra.js", members)
            self.assertNotIn(gate.BUNDLE + "/device-check.html", members)
            self.assertNotIn(gate.BUNDLE + "/nexus-stage-d-private-capture.cms", members)
            self.assertTrue(all(x.compress_type == zipfile.ZIP_STORED for x in zipped.infolist()))

    def test_public_astronomy_module_is_pinned_and_standalone_preserved(self):
        assets = gate.source_assets()
        vendor = assets[gate.ASTRONOMY_MODULE]
        self.assertEqual(gate.sha(vendor), "f41139a87941ea017ab902b954c9389fa27ea72083d7fab4971756d7769d14e6")
        self.assertIn(b'<script src="./vendor/astronomy-2.1.19.min.js" integrity="sha256-9BE5qHlB6gF6uQK5VMk4n6J+pyCD1/q0lxdW13adFOY="></script>', assets["index.html"])
        self.assertNotIn(vendor, assets["index.html"])
        self.assertIn(vendor, (HERE.parent / "web/studio.html").read_bytes())
        self.assertIn(gate.ASTRONOMY_MODULE.encode(), assets["service-worker.js"])
        # Keep the existing hard public HTML limit and check actual extraction
        # savings independently of unrelated, reviewed feature growth.
        tag = b'<script src="./vendor/astronomy-2.1.19.min.js" integrity="sha256-9BE5qHlB6gF6uQK5VMk4n6J+pyCD1/q0lxdW13adFOY="></script>'
        self.assertEqual(assets["index.html"].count(tag), 1)
        inline = assets["index.html"].replace(tag, b"<script>" + vendor + b"</script>", 1)
        self.assertGreater(len(inline) - len(assets["index.html"]), 100_000)
        self.assertLessEqual(len(assets["index.html"]), 650_000)

    def test_bad_commit_and_existing_outputs_refuse_overwrite(self):
        for sha in ("main", "b"*39, "", "D"*40):
            with self.subTest(sha=sha):
                with self.assertRaises(ValueError):
                    gate.build(self.archive, self.manifest_file, sha)
            self.assertFalse(self.archive.exists())
        self.archive.write_bytes(b"preserve-original")
        with self.assertRaises(ValueError):
            gate.build(self.archive, self.manifest_file, COMMIT)
        self.assertEqual(self.archive.read_bytes(), b"preserve-original")
        self.assertFalse(self.manifest_file.exists())

    def test_mutated_bytes_extra_member_and_wrong_source_commit_block(self):
        self.build()
        with zipfile.ZipFile(self.archive) as zipped:
            original = {x.filename: zipped.read(x) for x in zipped.infolist()}
        mutated = self.directory / "mutated.zip"
        with zipfile.ZipFile(mutated, "w") as zipped:
            for name, data in original.items():
                if name.endswith("/index.html"):
                    data += b"<!-- UNSIGNED CHANGE -->"
                zipped.writestr(name, data)
        with self.assertRaises(ValueError):
            gate.verify(mutated, self.manifest_file)
        with zipfile.ZipFile(mutated, "w") as zipped:
            for name, data in original.items():
                info = zipfile.ZipInfo(name, gate.STAMP)
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                zipped.writestr(info, data)
            zipped.writestr(gate.BUNDLE+"/secrets/provider.env", b"synthetic_only")
        with self.assertRaises(ValueError):
            gate.verify(mutated, self.manifest_file)
        with self.assertRaises(ValueError):
            gate.verify(self.archive, self.manifest_file, "d"*40)

    def test_forged_release_authority_and_wrong_digest_block(self):
        self.build()
        before = json.loads(self.manifest_file.read_bytes())
        for key, value in (
            ("readiness", "PRODUCTION_READY"),
            ("production_promotion_authorized", True),
            ("render_deploy_performed", True),
            ("zip_sha256", "f"*64),
            ("content_count", 99),
        ):
            with self.subTest(key=key):
                changed = dict(before)
                changed[key] = value
                self.manifest_file.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):
                    gate.verify(self.archive, self.manifest_file)
        self.manifest_file.write_text(json.dumps(before))
        self.assertEqual(gate.verify(self.archive, self.manifest_file), before)

    def test_bounded_public_comparison_reports_drift_and_unreachable(self):
        manifest = self.build()
        assets = gate.source_assets()
        result = gate.observe_public(manifest, lambda name: assets[name])
        self.assertEqual(result["status"], "SOURCE_MATCH_ONLY")
        self.assertEqual(result["observed_asset_count"], 10)
        self.assertTrue(all(x["status"] == "MATCH" for x in result["assets"]))
        for key in ("production_promotion_authorized", "render_deploy_performed",
                    "actual_deploy_identified", "real_browser_offline_verified"):
            self.assertIs(result[key], False)
        self.assertIs(result["read_only"], True)
        def corrupted(name):
            return b"OLD_PUBLIC" if name == "index.html" else assets[name]
        result = gate.observe_public(manifest, corrupted)
        self.assertEqual(result["status"], "PUBLIC_SOURCE_DRIFT")
        self.assertEqual([x["name"] for x in result["assets"] if x["status"] == "DRIFT"],
                         ["index.html"])
        def unavailable(name):
            if name == "service-worker.js":
                raise TimeoutError("synthetic_unreachable")
            return assets[name]
        result = gate.observe_public(manifest, unavailable)
        self.assertEqual(result["status"], "INCOMPLETE_PUBLIC_OBSERVATION")
        self.assertEqual([x["name"] for x in result["assets"] if x["status"] == "UNREACHABLE"],
                         ["service-worker.js"])

    def test_forged_external_observation_manifest_blocks_before_public_fetch(self):
        original = self.build()
        attempts = []
        def trap(name):
            attempts.append(name)
            return b"UNTRUSTED_NETWORK"
        forged = json.loads(json.dumps(original))
        forged["assets"]["index.html"]["sha256"] = "a" * 64
        with self.assertRaises(ValueError):
            gate.observe_public(forged, trap)
        forged = json.loads(json.dumps(original))
        forged["origin_to_compare"] = "https://unreviewed.invalid/"
        with self.assertRaises(ValueError):
            gate.observe_public(forged, trap)
        forged = json.loads(json.dumps(original))
        forged["production_promotion_authorized"] = True
        with self.assertRaises(ValueError):
            gate.observe_public(forged, trap)
        self.assertEqual(attempts, [], "never query public network with forged manifest")

    def test_public_live_fetch_is_fixed_origin_allowlist(self):
        with self.assertRaises(ValueError):
            gate.live_fetch("../secrets")
        with self.assertRaises(ValueError):
            gate.live_fetch("not-a-public-asset.json")
        self.assertEqual(gate.ORIGIN, "https://nexus-studio-merikation.onrender.com/")


if __name__ == "__main__":
    unittest.main(verbosity=2)
