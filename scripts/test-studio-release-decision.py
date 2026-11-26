#!/usr/bin/env python3
"""Synthetic-only negative fixtures for non-authoritative Studio release decisions."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(name, module_name):
    spec = importlib.util.spec_from_file_location(module_name, HERE / name)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


gate = load("studio-static-release-gate.py", "reviewed_studio_gate")
observer = load("studio-full-origin-observer.py", "reviewed_studio_full_observer")
review = load("studio-release-decision.py", "reviewed_studio_decision")
COMMIT = "f" * 40


class StudioDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.working = tempfile.TemporaryDirectory(prefix="studio-review-decision-synthetic-")
        cls.root = Path(cls.working.name)
        cls.bundle = cls.root / "candidate.zip"
        cls.manifest_path = cls.root / "candidate.json"
        gate.build(cls.bundle, cls.manifest_path, COMMIT)
        cls.manifest = json.loads(cls.manifest_path.read_text())
        cls.assets = gate.source_assets()
        cls.baseline = observer.observe_verified(
            cls.bundle, cls.manifest_path, COMMIT,
            fetch=lambda path: cls.assets[path],
        )

    @classmethod
    def tearDownClass(cls):
        cls.working.cleanup()

    def evaluate(self, data):
        return review.evaluate(
            manifest=self.manifest, observation=data,
            source_commit=COMMIT,
        )

    def test_all_20_match_still_holds_provider_identity_rollback_and_owner_approval(self):
        record = self.evaluate(self.baseline)
        self.assertEqual(record["status"], "HOLD_PROVIDER_RECOVERY_AND_OWNER_EVIDENCE")
        self.assertEqual(record["public_source_status"], "SOURCE_MATCH_ONLY")
        self.assertEqual(record["checked_paths"], 20)
        self.assertEqual(record["problems"], [])
        self.assertIn("CURRENT_RENDER_DEPLOY_ID_NOT_INDEPENDENTLY_VERIFIED", record["blockers"])
        self.assertIn("RENDER_ROLLBACK_ARTIFACT_NOT_CONFIRMED", record["blockers"])
        self.assertIn("SERVICE_SPECIFIC_OWNER_RELEASE_APPROVAL_REQUIRED", record["blockers"])
        self.assertTrue(record["source_manifest_and_zip_verified"])
        for key in ("render_deploy_identity_confirmed", "render_rollback_artifact_confirmed",
                    "production_recovery_tested", "real_owner_device_verified",
                    "provider_model_billing_verified", "owner_release_approval_confirmed",
                    "deployment_attempted", "service_configuration_mutated",
                    "ready_to_promote"):
            self.assertIs(record[key], False)
        self.assertEqual(record["authority"], "none")

    def test_html_and_worker_drift_produce_targeted_non_release_summary(self):
        def stale(path):
            return b"old-public-file" if path in ("index.html", "service-worker.js") else self.assets[path]
        observation = observer.observe_verified(
            self.bundle, self.manifest_path, COMMIT, fetch=stale
        )
        record = self.evaluate(observation)
        self.assertEqual(record["status"], "HOLD_PUBLIC_SOURCE_DRIFT")
        self.assertEqual(record["public_source_status"], "PUBLIC_SOURCE_DRIFT")
        self.assertEqual(record["problems"], [
            {"path": "index.html", "result": "DRIFT"},
            {"path": "service-worker.js", "result": "DRIFT"},
        ])
        self.assertIn("PUBLIC_ASSETS_DIFFER_FROM_CANDIDATE", record["blockers"])
        self.assertFalse(record["ready_to_promote"])

    def test_missing_pdf_worker_forces_incomplete_witness_not_drift_or_go(self):
        def broken(path):
            if path == "pdf/pdf.worker.min.mjs":
                raise TimeoutError("private fixture exception")
            return self.assets[path]
        observation = observer.observe_verified(
            self.bundle, self.manifest_path, COMMIT, fetch=broken
        )
        record = self.evaluate(observation)
        self.assertEqual(record["status"], "HOLD_PUBLIC_OBSERVATION_INCOMPLETE")
        self.assertEqual(record["public_source_status"], "INCOMPLETE_PUBLIC_OBSERVATION")
        self.assertEqual(record["problems"], [
            {"path": "pdf/pdf.worker.min.mjs", "result": "UNREACHABLE"}])
        self.assertNotIn("private fixture exception", json.dumps(record))

    def test_legacy_only_observation_cannot_authorize_current_candidate(self):
        obj = copy.deepcopy(self.baseline)
        legacy_missing = {"vendor/astronomy-2.1.19.min.js", "studio-orchestra.js", "studio-reply-format.js"}
        obj["assets"] = [asset for asset in obj["assets"] if asset["path"] not in legacy_missing]
        obj["observed_public_files"] = 17
        obj["reviewed_public_files"] = 17
        self.assertEqual(len(obj["assets"]), 17)
        self.assert_blocked(obj)

    def test_previous_18_asset_observation_cannot_authorize_current_candidate(self):
        obj = copy.deepcopy(self.baseline)
        obj["assets"] = [asset for asset in obj["assets"] if asset["path"] not in {"studio-orchestra.js", "studio-reply-format.js"}]
        obj["observed_public_files"] = 18
        obj["reviewed_public_files"] = 18
        self.assertEqual(len(obj["assets"]), 18)
        self.assert_blocked(obj)

    def test_icon_pixel_match_is_allowed_but_cannot_release(self):
        obs = copy.deepcopy(self.baseline)
        obs["assets"][3]["status"] = "PIXEL_MATCH"  # Indexed by reviewed FILES inventory.
        self.assertIn(obs["assets"][3]["path"], review.ICONS)
        decision = self.evaluate(obs)
        self.assertEqual(decision["status"], "HOLD_PROVIDER_RECOVERY_AND_OWNER_EVIDENCE")
        self.assertIs(decision["ready_to_promote"], False)

    def assert_blocked(self, obs):
        with self.assertRaises(review.UntrustedReleaseEvidence):
            self.evaluate(obs)

    def test_forged_grant_extra_content_and_inconsistent_counts_are_rejected(self):
        edits = (
            ("status", "PRODUCTION_READY"),
            ("source_commit", "0"*40),
            ("fixed_public_origin", "https://attacker.invalid/"),
            ("source_manifest_verified", False),
            ("read_only", False),
            ("render_deploy_id_verified", True),
            ("public_browser_verified", True),
            ("rollback_provider_artifact_verified", True),
            ("production_promotion_authorized", True),
            ("provider_mutation", True),
            ("private_user_data_seen", True),
            ("authority", "owner"),
            ("observed_public_files", 16),
            ("reviewed_public_files", 100),
        )
        for key, value in edits:
            with self.subTest(key=key):
                obj = copy.deepcopy(self.baseline)
                obj[key] = value
                self.assert_blocked(obj)
        obj = copy.deepcopy(self.baseline)
        obj["api_key"] = "should-not-ever-emit"
        self.assert_blocked(obj)

    def test_duplicate_reordered_nonicon_pixel_and_unexpected_status_rejected(self):
        for kind in ("duplicate", "reorder", "unknown", "pixel", "private"):
            with self.subTest(kind=kind):
                obj = copy.deepcopy(self.baseline)
                if kind == "duplicate":
                    obj["assets"][1] = obj["assets"][0]
                elif kind == "reorder":
                    obj["assets"].reverse()
                elif kind == "unknown":
                    obj["assets"][0]["status"] = "PASS"
                elif kind == "pixel":
                    obj["assets"][0]["status"] = "PIXEL_MATCH"  # HTML is never pixel-equivalent.
                else:
                    obj["assets"][0]["raw_response"] = "private user text"
                self.assert_blocked(obj)

    def test_observation_drift_claim_must_match_actual_asset_records(self):
        obj = copy.deepcopy(self.baseline)
        obj["status"] = "PUBLIC_SOURCE_DRIFT"
        self.assert_blocked(obj)
        obj = copy.deepcopy(self.baseline)
        obj["assets"][0]["status"] = "DRIFT"
        self.assert_blocked(obj)

    def test_zip_manifest_or_revision_mismatch_blocks_before_summary(self):
        obj = copy.deepcopy(self.baseline)
        with self.assertRaises(ValueError):
            review.check(self.bundle, self.manifest_path, self.root / "missing.json", "a"*40)
        fake = self.root / "fake-original.json"
        forged = copy.deepcopy(self.manifest)
        forged["source_commit"] = "b"*40
        fake.write_text(json.dumps(forged))
        with self.assertRaises(ValueError):
            review.check(self.bundle, fake, self.root / "missing.json", COMMIT)
        obj["source_commit"] = COMMIT

    def test_duplicate_json_keys_and_secret_paths_are_rejected_without_printing(self):
        fake = self.root / "bad-observation.json"
        fake.write_text('{"status":"SOURCE_MATCH_ONLY","status":"PUBLIC_SOURCE_DRIFT"}')
        with self.assertRaises(review.UntrustedReleaseEvidence):
            review.load_observation(fake)
        fake.write_bytes(b"x" * (review.MAX_INPUT + 1))
        with self.assertRaises(review.UntrustedReleaseEvidence):
            review.load_observation(fake)
        link = self.root / "symlink.json"
        link.symlink_to(fake)
        with self.assertRaises(review.UntrustedReleaseEvidence):
            review.load_observation(link)

    def test_cli_writes_hold_result_without_provider_call_or_private_error(self):
        report = self.root / "current-review.json"
        report.write_text(json.dumps(self.baseline))
        out = self.root / "release-hold-output.json"
        with patch("sys.argv", ["studio-release-decision",
                                "--zip", str(self.bundle),
                                "--manifest", str(self.manifest_path),
                                "--observation", str(report),
                                "--source-commit", COMMIT, "--out", str(out)]):
            self.assertEqual(review.main(), 0)
        result = json.loads(out.read_bytes())
        self.assertEqual(result["status"], "HOLD_PROVIDER_RECOVERY_AND_OWNER_EVIDENCE")
        self.assertFalse(result["ready_to_promote"])
        self.assertNotIn("key", str(result["problems"]))
        with patch("sys.argv", ["studio-release-decision",
                                "--zip", str(self.bundle),
                                "--manifest", str(self.manifest_path),
                                "--observation", str(report),
                                "--source-commit", COMMIT, "--out", str(out)]):
            self.assertEqual(review.main(), 2)
        self.assertFalse((self.root / "nonexistent.json").exists())

    def test_workflow_invokes_gate_without_secrets_or_render_mutation(self):
        wf = (HERE.parent / ".github/workflows/studio-static-source-release.yml").read_text()
        self.assertIn("studio-release-decision.py", wf)
        self.assertIn("test-studio-release-decision.py", wf)
        self.assertIn("nexus-studio-release-decision-hold.json", wf)
        self.assertIn("--source-commit \"$GITHUB_SHA\"", wf)
        self.assertIn("ready_to_promote", wf)
        self.assertNotIn("trigger_deploy", wf)


if __name__ == "__main__":
    unittest.main(verbosity=2)
