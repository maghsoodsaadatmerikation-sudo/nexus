#!/usr/bin/env python3
"""Offline negative and positive tests for untrusted Android self-report receipts."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from pilot12_android_receipt import (
    InvalidReceipt, ORIGIN, REQUIRED, SCHEMA, SOURCE_HASH, STAGES, MAX_BYTES,
    parse_document, validate,
)

ROOT = Path(__file__).resolve().parent.parent


def sample(complete: bool = True) -> dict:
    return {
        "schema": SCHEMA,
        "origin": ORIGIN,
        "app": "legacy-public-pilot12",
        "browser": "chrome",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds")
                      .replace("+00:00", "Z"),
        "stages": {key: "pass" if complete else "not_tested" for key in STAGES},
        "self_attested_physical_android": complete,
        "self_attested_fictional_only": complete,
        "reviewed_public_html_sha256": SOURCE_HASH,
        "device_sha256_measured": False,
        "independent_hardware_verified": False,
        "production_release_authorized": False,
        "authority": "none",
        "transmission": "none",
        "status": "USER_REPORTED_PASS_UNVERIFIED" if complete
                  else "INCOMPLETE_OR_FAILED",
    }


class ReceiptTests(unittest.TestCase):
    def test_complete_self_report_never_independent_pass(self):
        receipt = sample()
        report = parse_document(json.dumps(receipt).encode())
        self.assertEqual(report["review_verdict"], "PENDING_INDEPENDENT_REVIEW")
        self.assertEqual(report["reported_steps"], len(STAGES))
        self.assertFalse(report["real_android_hardware_independently_verified"])
        self.assertFalse(report["network_cut_independently_verified"])
        self.assertFalse(report["device_source_hash_independently_verified"])
        self.assertFalse(report["release_authorized"])
        self.assertEqual(report["authority"], "none")

    def test_incomplete_report_valid_but_not_accepted(self):
        receipt = sample(False)
        receipt["stages"]["online_exact_origin"] = "fail"
        report = validate(receipt)
        self.assertEqual(report["review_verdict"], "INCOMPLETE_OR_FAILED")
        self.assertEqual(report["reported_steps"], 0)
        self.assertFalse(report["release_authorized"])

    def test_reject_unknown_fields_that_may_carry_private_content(self):
        receipt = sample()
        receipt["device_identifier"] = "never-collect-this"
        with self.assertRaises(InvalidReceipt):
            validate(receipt)

    def test_reject_forged_source_and_hardware_authority(self):
        for key, value in (
            ("device_sha256_measured", True),
            ("independent_hardware_verified", True),
            ("production_release_authorized", True),
            ("authority", "owner"),
            ("origin", "https://elsewhere.example/"),
            ("app", "studio"),
            ("reviewed_public_html_sha256", "0" * 64),
            ("transmission", "uploaded"),
        ):
            with self.subTest(key=key):
                receipt = sample()
                receipt[key] = value
                with self.assertRaises(InvalidReceipt):
                    validate(receipt)

    def test_reject_duplicate_fields(self):
        raw = json.dumps(sample()).replace('"schema":', '"schema":"bogus","schema":', 1)
        with self.assertRaises(InvalidReceipt):
            parse_document(raw.encode())

    def test_reject_invalid_stages_and_false_pass_claims(self):
        for mutated in ("not_tested", "FAIL", True, None, "pass plus"):
            with self.subTest(value=mutated):
                receipt = sample()
                receipt["stages"]["reopen_two"] = mutated
                with self.assertRaises(InvalidReceipt):
                    validate(receipt)
        receipt = sample()
        receipt["self_attested_physical_android"] = False
        with self.assertRaises(InvalidReceipt):
            validate(receipt)
        receipt = sample(False)
        receipt["status"] = "PASS"
        with self.assertRaises(InvalidReceipt):
            validate(receipt)

    def test_invalid_time_and_oversized_data(self):
        receipt = sample()
        for timestamp in ("2026-99-40T00:00:00.000Z",
                          "1970-01-01T00:00:00.000Z",
                          "2999-01-01T00:00:00.000Z",
                          "2026-11-17 10:00:00"):
            with self.subTest(timestamp=timestamp):
                receipt["created_at"] = timestamp
                with self.assertRaises(InvalidReceipt):
                    validate(receipt)
        with self.assertRaises(InvalidReceipt):
            parse_document(b" " * (MAX_BYTES + 1))
        with self.assertRaises(InvalidReceipt):
            parse_document(b'{"x": NaN}')
        with self.assertRaises(InvalidReceipt):
            parse_document(b"\xff")

    def test_schema_exact(self):
        self.assertEqual(len(REQUIRED), len(sample()))
        self.assertEqual(len(STAGES), 10)
        with self.assertRaises(InvalidReceipt):
            validate({})
        with self.assertRaises(InvalidReceipt):
            parse_document(b"[]")

    def test_form_has_no_network_data_collection_or_persistence(self):
        html = (ROOT / "web/pilot12-android-field-witness.html").read_text("utf-8")
        self.assertIn("connect-src 'none'", html)
        self.assertIn("form-action 'none'", html)
        self.assertIn("legacy-public-pilot12", html)
        self.assertIn("USER_REPORTED_PASS_UNVERIFIED", html)
        self.assertIn("independent_hardware_verified:false", html)
        self.assertIn("device_sha256_measured:false", html)
        self.assertIn("production_release_authorized:false", html)
        self.assertIn("transmission:'none'", html)
        self.assertIn(SOURCE_HASH, html)
        self.assertEqual(len(re.findall(r"<script>", html)), 1)
        script = re.search(r"<script>([\s\S]*?)</script>", html)
        self.assertIsNotNone(script)
        for forbidden in ("fetch(", "XMLHttpRequest", "sendBeacon",
                          "WebSocket", "localStorage", "sessionStorage",
                          "new Worker(", "import(", "eval("):
            self.assertNotIn(forbidden, script.group(1))
        self.assertEqual(len(re.findall(r"self_attested_physical_android", html)), 1)

    def test_static_script_javascript_is_syntactically_valid(self):
        if not shutil.which("node"):
            self.skipTest("Node not installed")
        html = (ROOT / "web/pilot12-android-field-witness.html").read_text("utf-8")
        script = re.search(r"<script>([\s\S]*?)</script>", html).group(1)
        with tempfile.TemporaryDirectory(prefix="nexus-pilot12-android-") as tmp:
            path = Path(tmp, "safe-witness.js")
            path.write_text(script, "utf-8")
            subprocess.run(["node", "--check", str(path)], check=True,
                           capture_output=True, timeout=12)

    def test_reviewed_baseline_matches_source_without_network(self):
        html = (ROOT / "web/offline-pilot.html").read_bytes()
        sw = (ROOT / "public/service-worker.js").read_text("utf-8")
        self.assertEqual(hashlib.sha256(html).hexdigest(), SOURCE_HASH)
        self.assertIn("const EXPECTED_SHA256='" + SOURCE_HASH + "'", sw)


if __name__ == "__main__":
    unittest.main(verbosity=2)
