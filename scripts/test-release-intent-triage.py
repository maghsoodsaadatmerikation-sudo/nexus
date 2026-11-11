#!/usr/bin/env python3
"""Synthetic-only tests: blocked release intent is NOT a release verification."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("triage-release-intent.py")
spec = importlib.util.spec_from_file_location("gate_triage", SCRIPT)
triage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(triage)
SHA = "a" * 40


def synthetic():
    return {
        "schema": triage.SCHEMA,
        "sha": SHA,
        "commit_message": "fix(stage-d): synthetic non-release metadata",
        "runs": [{
            "version": version,
            "name": f"NEXUS {version} Release Gate",
            "head_sha": SHA,
            "status": "completed",
            "conclusion": "failure",
            "failed_steps": [step],
        } for version, (step, _intent) in triage.EXPECTED.items()],
    }


class ReleaseIntentTriageTests(unittest.TestCase):
    def test_seven_exact_intent_refusals_are_a_non_release_diagnosis_only(self):
        d = synthetic()
        report = triage.classify(d)
        self.assertEqual(report["status"], "EXPECTED_INTENT_REFUSALS_ONLY")
        self.assertEqual(report["observed_refusal_count"], 7)
        self.assertEqual(set(report["classified_versions"]), set(triage.EXPECTED))
        self.assertIs(report["release_authorized"], False)
        self.assertIs(report["seal_granted"], False)
        self.assertEqual(report["authority"], "none")
        self.assertEqual(report["real_backup"], "not_evaluated")
        self.assertEqual(report["production_recovery"], "not_evaluated")
        self.assertNotIn("PASS", json.dumps(report))

    def assert_refused(self, document):
        with self.assertRaises(triage.EvidenceBlocked):
            triage.classify(document)

    def test_missing_gate_cannot_be_called_complete(self):
        d = synthetic()
        d["runs"].pop()
        self.assert_refused(d)

    def test_duplicate_gate_cannot_mask_a_missing_gate(self):
        d = synthetic()
        d["runs"][0] = d["runs"][1].copy()
        self.assert_refused(d)

    def test_mismatched_exact_sha_rejected(self):
        d = synthetic()
        d["runs"][3]["head_sha"] = "b" * 40
        self.assert_refused(d)

    def test_unexpected_failing_step_is_not_expected_refusal(self):
        d = synthetic()
        d["runs"][3]["failed_steps"] = ["Build or security test failed"]
        self.assert_refused(d)

    def test_multiple_failed_steps_are_not_expected_refusal(self):
        d = synthetic()
        d["runs"][2]["failed_steps"].append("Unknown later failure")
        self.assert_refused(d)

    def test_success_or_cancelled_gate_is_not_expected_refusal(self):
        for result in ("success", "cancelled", "skipped"):
            d = synthetic()
            d["runs"][1]["conclusion"] = result
            self.assert_refused(d)

    def test_in_progress_cannot_be_called_refusal(self):
        d = synthetic()
        d["runs"][0]["status"] = "in_progress"
        self.assert_refused(d)

    def test_matching_authorized_release_intent_is_never_called_expected_failure(self):
        for v, (_step, intent) in triage.EXPECTED.items():
            with self.subTest(version=v):
                d = synthetic()
                d["commit_message"] = intent
                self.assert_refused(d)

    def test_unknown_workflow_name_is_refused(self):
        d = synthetic()
        d["runs"][0]["name"] = "Other workflow"
        self.assert_refused(d)

    def test_unrecognized_version_is_refused(self):
        d = synthetic()
        d["runs"][0]["version"] = "v9.9"
        self.assert_refused(d)

    def test_bad_envelope_or_sha_is_refused(self):
        for edit in ({"schema": "other"}, {"sha": "not-40-hex"},
                     {"extra": "unknown"}, {"commit_message": ""}):
            d = synthetic()
            d.update(edit)
            self.assert_refused(d)

    def test_report_does_not_reflect_private_commit_text(self):
        d = synthetic()
        d["commit_message"] = "PRIVATE_COMMIT_MESSAGE_SENTINEL"
        report = triage.classify(d)
        self.assertNotIn("PRIVATE_COMMIT_MESSAGE_SENTINEL", json.dumps(report))

    def test_cli_never_echoes_untrusted_contents_or_paths(self):
        with tempfile.TemporaryDirectory() as root:
            evidence = Path(root) / "PRIVATE_PATH_SENTINEL.json"
            evidence.write_text(json.dumps(synthetic()), encoding="utf-8")
            good = subprocess.run([sys.executable, str(SCRIPT), str(evidence)],
                                  capture_output=True, text=True, timeout=5)
            self.assertEqual(good.returncode, 0, good.stderr)
            self.assertIs(json.loads(good.stdout)["release_authorized"], False)
            d = synthetic()
            d["runs"][0]["failed_steps"] = ["PRIVATE_FAILURE_SENTINEL"]
            evidence.write_text(json.dumps(d), encoding="utf-8")
            bad = subprocess.run([sys.executable, str(SCRIPT), str(evidence)],
                                 capture_output=True, text=True, timeout=5)
            self.assertNotEqual(bad.returncode, 0)
            self.assertEqual(bad.stdout, "")
            for private in ("PRIVATE_PATH_SENTINEL", "PRIVATE_FAILURE_SENTINEL"):
                self.assertNotIn(private, bad.stderr)

    def test_duplicate_json_keys_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / "bad.json"
            p.write_text('{"schema":"x","schema":"y"}', encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), str(p)],
                                    capture_output=True, text=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")

    def test_symlinked_or_oversize_input_blocked(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / "source.json"
            p.write_text(json.dumps(synthetic()), encoding="utf-8")
            link = Path(root) / "alias.json"
            link.symlink_to(p)
            for item in (link,):
                result = subprocess.run([sys.executable, str(SCRIPT), str(item)],
                                        capture_output=True, text=True, timeout=5)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
            p.write_bytes(b"X" * (128 * 1024 + 1))
            result = subprocess.run([sys.executable, str(SCRIPT), str(p)],
                                    capture_output=True, text=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
