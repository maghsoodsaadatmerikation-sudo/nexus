#!/usr/bin/env python3
"""Synthetic negative fixtures for public Studio post-promotion acceptance."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).with_name("verify-studio-public-acceptance.py")
spec = importlib.util.spec_from_file_location("studio_public_acceptance", SOURCE)
target = importlib.util.module_from_spec(spec)
spec.loader.exec_module(target)
HASH = "a" * 64
SHA = "b" * 40
CHECKS = sorted(target.REQUIRED_CHECKS) + [f"synthetic-browser-condition-{i}" for i in range(14)]
MODEL_CHECKS = [
    "actual-model-uses-supplied-fact-in-english",
    "browser-network-offline-before-inference",
    "actual-inference-report-excludes-answer-text",
    "cancel-terminates-real-inference-worker",
    "oversized-context-rejected-without-truncation",
]


class PublicAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.model_manifest = json.loads(
            (target.ROOT / "public/studio/device/model-manifest.json").read_text())
        self.assets = {
            "status": "PASS",
            "origin": target.ORIGIN.rstrip("/"),
            "authority": "none",
            "production_mutation": False,
            "user_data_seen": False,
            "server_credentials_used": False,
            "verified_resources": 9,
            "resources": {},
        }
        for k in target.ASSET_KEYS:
            self.assets["resources"][k] = {
                "http_status": 200,
                "ok": True,
                "sha256": HASH,
                "expected_sha256": HASH,
                "exact_byte_match": True,
                "pixel_match": True,
            }
        self.browser = {
            "status": "PASS",
            "origin": target.ORIGIN,
            "source_sha256": HASH,
            "authority": "none",
            "actual_offline_navigation": True,
            "real_android_hardware": False,
            "real_model_tested": False,
            "checks": CHECKS,
        }
        self.model = {
            "status": "PASS",
            "origin": target.ORIGIN,
            "authority": "none",
            "real_android_hardware": False,
            "real_model_tested": True,
            "model": self.model_manifest["model"],
            "revision": self.model_manifest["revision"],
            "runtime": self.model_manifest["runtime"],
            "download_bytes": 120_000_000,
            "checks": MODEL_CHECKS,
            "output": "SYNTHETIC GREEN ANSWER -- OMIT FROM RELEASE WITNESS",
        }

    def attempt(self, assets=None, first=None, second=None, model=None):
        return target.build_report(
            assets if assets is not None else self.assets,
            first if first is not None else self.browser,
            second if second is not None else self.browser,
            model if model is not None else self.model,
            HASH, self.model_manifest, commit=SHA)

    def test_accepts_two_exact_public_sessions_without_leaking_synthetic_output(self):
        result = self.attempt()
        self.assertEqual(result["status"], "PUBLIC_CHROMIUM_ACCEPTED")
        self.assertEqual(result["independent_fresh_chromium_runs"], 2)
        self.assertEqual(result["source_commit"], SHA)
        self.assertEqual(result["checked_public_paths"], 9)
        self.assertEqual(result["source_sha256"], HASH)
        self.assertEqual(result["pinned_model_revision"], self.model_manifest["revision"])
        for flag in ("actual_render_deploy_id_verified", "render_deploy_performed",
                     "real_android_hardware_verified", "production_seal",
                     "private_user_data_used", "provider_token_used",
                     "owner_promotion_authorized"):
            self.assertIs(result[flag], False)
        self.assertEqual(result["authority"], "none")
        self.assertNotIn("SYNTHETIC GREEN", json.dumps(result))

    def test_fails_public_identity_and_unauthorized_asset_changes(self):
        for key, value in (
            ("status", "FAIL_CLOSED"),
            ("origin", "https://other.example"),
            ("authority", "verified"),
            ("production_mutation", True),
            ("server_credentials_used", True),
            ("verified_resources", 8),
        ):
            altered = copy.deepcopy(self.assets)
            altered[key] = value
            with self.subTest(key=key), self.assertRaises(target.WitnessError):
                self.attempt(assets=altered)
        altered = copy.deepcopy(self.assets)
        altered["resources"]["/"]["sha256"] = "f" * 64
        with self.assertRaises(target.WitnessError):
            self.attempt(assets=altered)
        altered = copy.deepcopy(self.assets)
        altered["resources"]["/service-worker.js"]["exact_byte_match"] = False
        with self.assertRaises(target.WitnessError):
            self.attempt(assets=altered)
        altered = copy.deepcopy(self.assets)
        altered["resources"].pop("/device/model-manifest.json")
        with self.assertRaises(target.WitnessError):
            self.attempt(assets=altered)

    def test_rejects_incomplete_or_forged_real_browser_sessions(self):
        for key, value in (
            ("status", "PASS_OTHER"),
            ("actual_offline_navigation", False),
            ("source_sha256", "c" * 64),
            ("real_android_hardware", True),
            ("origin", "http://127.0.0.1:8765/"),
            ("authority", "production"),
        ):
            altered = copy.deepcopy(self.browser)
            altered[key] = value
            with self.subTest(key=key), self.assertRaises(target.WitnessError):
                self.attempt(second=altered)
        altered = copy.deepcopy(self.browser)
        altered["checks"].remove("corrupted-offline-shell-rejected")
        with self.assertRaises(target.WitnessError):
            self.attempt(second=altered)
        altered = copy.deepcopy(self.browser)
        altered["checks"].append("unexpected-new-success")
        with self.assertRaises(target.WitnessError):
            self.attempt(second=altered)

    def test_rejects_unpinned_or_simulated_model(self):
        for key, value in (
            ("status", "FAIL"),
            ("model", "unreviewed/model"),
            ("revision", "head"),
            ("runtime", "cloud"),
            ("real_model_tested", False),
            ("authority", "operator"),
            ("download_bytes", 0),
        ):
            altered = copy.deepcopy(self.model)
            altered[key] = value
            with self.subTest(key=key), self.assertRaises(target.WitnessError):
                self.attempt(model=altered)
        altered = copy.deepcopy(self.model)
        altered["checks"].remove("browser-network-offline-before-inference")
        with self.assertRaises(target.WitnessError):
            self.attempt(model=altered)

    def test_rejects_invalid_revision_and_missing_files(self):
        with self.assertRaises(target.WitnessError):
            target.build_report(self.assets, self.browser, self.browser,
                                self.model, HASH, self.model_manifest, commit="main")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.json"
            with self.assertRaises(target.WitnessError):
                target.load_json(path)
            path.write_text("not json")
            with self.assertRaises(json.JSONDecodeError):
                target.load_json(path)
            path.write_text("{}")
            self.assertEqual(target.load_json(path), {})
            path.write_text("{" + "x" * 36000)
            with self.assertRaises(target.WitnessError):
                target.load_json(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
