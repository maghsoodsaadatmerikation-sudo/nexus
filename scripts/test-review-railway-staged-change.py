#!/usr/bin/env python3
"""Synthetic-only tests for Phase 34. No network, Railway credentials or writes."""
import copy
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("review-railway-staged-change.py").resolve()
spec = importlib.util.spec_from_file_location("review", SCRIPT)
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)
NOW = dt.datetime(2026, 11, 17, 10, tzinfo=dt.timezone.utc)


def fixture():
    data = {
        "schema": review.SCHEMA,
        "captured_at_utc": NOW.isoformat(),
        "staged_changes": {
            "project": {"id": review.PROJECT, "name": "NEXUS Stage D"},
            "environment": {"id": review.ENVIRONMENT, "name": "production"},
            "staged": {"patchId": review.PATCH, "status": "STAGED", "changeCount": 2,
                       "updatedAt": "2026-11-13T14:34:50.369Z"},
            "destructive": False,
            "resources": [{"kind": "service", "id": review.SERVICE,
                           "name": "nexus-stage-d", "action": "update",
                           "changes": [{"path": k, **v} for k, v in review.EXPECTED.items()]}],
            "sharedVariables": [], "privateNetworkDisabled": None,
        }
    }
    return data


def run(data):
    return review.inspect(data, now=NOW)


class ReviewTests(unittest.TestCase):
    def test_exact_known_patch_is_reviewable_not_authorized(self):
        r = run(fixture())
        self.assertEqual(r["exact_diff_review"], "MATCH")
        self.assertEqual(r["next_action"], "HUMAN_REVIEW_REQUIRED")
        self.assertFalse(r["deployment_authorized"])
        self.assertFalse(r["production_mutation"])
        self.assertIn("patch_unchanged_for_over_72_hours", r["alerts"])

    def test_same_source_field_different_value_blocks(self):
        for key, value in (("from", "/tampered"), ("to", "/"), ("destructive", True), ("type", "added")):
            with self.subTest(key=key):
                d = fixture()
                d["staged_changes"]["resources"][0]["changes"][0][key] = value
                self.assertEqual(run(d)["exact_diff_review"], "BLOCKED")

    def test_mutated_target_or_patch_blocks(self):
        for container, key in (("project", "id"), ("environment", "id"), ("staged", "patchId"), ("staged", "status")):
            with self.subTest(container=container, key=key):
                d = fixture()
                d["staged_changes"][container][key] = "wrong"
                self.assertEqual(run(d)["exact_diff_review"], "BLOCKED")

    def test_extra_resource_changed_field_and_duplicates_block(self):
        d = fixture()
        d["staged_changes"]["resources"].append(copy.deepcopy(d["staged_changes"]["resources"][0]))
        self.assertEqual(run(d)["exact_diff_review"], "BLOCKED")
        d = fixture()
        d["staged_changes"]["resources"][0]["changes"][1] = copy.deepcopy(d["staged_changes"]["resources"][0]["changes"][0])
        self.assertEqual(run(d)["exact_diff_review"], "BLOCKED")
        d = fixture()
        d["staged_changes"]["resources"][0]["changes"][0]["newProp"] = "ignored?"
        self.assertEqual(run(d)["exact_diff_review"], "BLOCKED")

    def test_network_variable_destructive_and_unknown_fields(self):
        for key, value in (("sharedVariables", [{"x": "y"}]), ("privateNetworkDisabled", {"type": "updated"}), ("destructive", True)):
            with self.subTest(key=key):
                d = fixture()
                d["staged_changes"][key] = value
                self.assertEqual(run(d)["exact_diff_review"], "BLOCKED")
        for key in ("sharedVariables", "privateNetworkDisabled", "destructive", "resources", "staged"):
            with self.subTest(missing=key):
                d = fixture()
                del d["staged_changes"][key]
                if key == "staged":
                    with self.assertRaises(review.InvalidCapture):
                        run(d)
                else:
                    self.assertEqual(run(d)["exact_diff_review"], "BLOCKED")

    def test_missing_count_or_nonint_count_blocks(self):
        for value in (None, True, 1, "2", 3):
            d = fixture()
            d["staged_changes"]["staged"]["changeCount"] = value
            self.assertEqual(run(d)["exact_diff_review"], "BLOCKED")

    def test_stale_capture_and_future_patch_block(self):
        d = fixture()
        d["captured_at_utc"] = "2026-11-16T00:00:00Z"
        self.assertEqual(run(d)["exact_diff_review"], "BLOCKED")
        d = fixture()
        d["staged_changes"]["staged"]["updatedAt"] = "2026-12-01T00:00:00Z"
        self.assertEqual(run(d)["exact_diff_review"], "BLOCKED")

    def test_input_no_symlink_hardlink_and_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.json"
            p.write_text('{"schema":"nexus.railway-staged-patch-capture.v1","schema":"poison"}')
            with self.assertRaises(review.InvalidCapture):
                review.load(p)
            p.write_text(json.dumps(fixture()))
            p.chmod(0o600)
            self.assertEqual(review.load(p)["schema"], review.SCHEMA)
            link = Path(tmp) / "linked"
            link.symlink_to(p)
            with self.assertRaises(review.InvalidCapture):
                review.load(link)
            p2 = Path(tmp) / "hardlinked"
            os.link(p, p2)
            with self.assertRaises(review.InvalidCapture):
                review.load(p)
            p2.unlink()
            p.chmod(0o644)
            with self.assertRaises(review.InvalidCapture):
                review.load(p)
            p.chmod(0o600)
            p.write_bytes(b"X" * (review.MAX_BYTES + 1))
            with self.assertRaises(review.InvalidCapture):
                review.load(p)

    def test_cli_does_not_echo_private_provider_extras(self):
        d = fixture()
        d["staged_changes"]["extra"] = "SENTINEL_PRIVATE"
        d["captured_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "sample.json"
            p.write_text(json.dumps(d))
            p.chmod(0o600)
            result = subprocess.run([sys.executable, str(SCRIPT), "--input", str(p)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("SENTINEL_PRIVATE", result.stdout + result.stderr)
            result_data = json.loads(result.stdout)
            self.assertFalse(result_data["deployment_authorized"])


if __name__ == "__main__":
    unittest.main()
