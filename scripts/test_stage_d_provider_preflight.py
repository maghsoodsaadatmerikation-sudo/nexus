#!/usr/bin/env python3
"""Tests for non-authorizing Stage D release metadata triage."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts/stage_d_provider_preflight.py"
spec = importlib.util.spec_from_file_location("stage_d_provider_preflight", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SNAPSHOT = ROOT / "evidence/stage-d-provider-metadata-2026-11-17.json"


def sample():
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


class ProviderPreflightTests(unittest.TestCase):
    def test_current_recorded_drift_is_a_block_not_a_release(self):
        report = module.triage(sample())
        self.assertEqual(report["status"],
                         "HOLD_INDEPENDENT_RUNTIME_AND_RECOVERY_EVIDENCE")
        self.assertEqual(report["source_conflicts"], {
            "repo_main_vs_reported_railway": True,
            "historical_v17_target_vs_reported_railway": True,
            "repo_main_vs_historical_v17_target": True,
        })
        self.assertTrue(report["staged_config_present"])
        self.assertTrue(report["staged_healthcheck_change"])
        self.assertTrue(report["reported_sleep_application"])
        self.assertTrue(report["reported_volume_mounted"])
        for key in ("live_http_identity_independently_verified",
                    "recovery_independently_verified", "release_authorized",
                    "seal_granted", "production_mutation",
                    "paid_mutation_authorized",
                    "current_main_at_runtime_checked"):
            self.assertIs(report[key], False)

    def test_even_all_sources_equal_remains_on_hold(self):
        data = sample()
        data["railway_live_source"] = data["github_main_at_observation"]
        data["historical_v17_gate_target"] = data["github_main_at_observation"]
        data["staged_healthcheck_path"] = "none"
        data["staged_change_count"] = 0
        data["sleep_application_enabled"] = False
        data["railway_deployment_status"] = "SUCCESS"
        report = module.triage(data)
        self.assertEqual(report["status"],
                         "HOLD_INDEPENDENT_RUNTIME_AND_RECOVERY_EVIDENCE")
        self.assertFalse(any(report["source_conflicts"].values()))
        self.assertFalse(report["staged_config_present"])
        self.assertFalse(report["release_authorized"])

    def test_cannot_forge_runtime_restore_or_release_claims(self):
        for key,value in (
            ("runtime_identity_observed", True),
            ("independent_volume_restore_observed", True),
            ("provider_metadata_only", False),
            ("provider", "Cloudflare"),
            ("service", "studio"),
            ("environment", "preview"),
            ("durable_mount_path", "/root"),
            ("railway_deployment_status", "SEALED"),
            ("staged_change_count", -1),
            ("sleep_application_enabled", "false"),
        ):
            with self.subTest(key=key):
                data = sample()
                data[key] = value
                with self.assertRaises(module.InvalidSnapshot):
                    module.triage(data)
        data = sample()
        data["release_authorized"] = True
        with self.assertRaises(module.InvalidSnapshot):
            module.triage(data)

    def test_invalid_and_malformed_source_identity_rejected(self):
        for key in ("github_main_at_observation",
                    "historical_v17_gate_target", "railway_live_source"):
            for value in ("a" * 39, "g" * 40, "", None, 7, ["a" * 40]):
                with self.subTest(key=key,value=repr(value)[:20]):
                    d = sample()
                    d[key] = value
                    with self.assertRaises(module.InvalidSnapshot):
                        module.triage(d)

    def test_invalid_observed_date_rejected(self):
        for d in ("2026-02-30", "2030-01-01", "2024-01-01", "today",
                  "2026-11-17T00:00:00Z"):
            with self.subTest(date=d):
                data = sample()
                data["observed_date"] = d
                with self.assertRaises(module.InvalidSnapshot):
                    module.triage(data)

    def test_missing_duplicate_extra_or_sensitive_fields_rejected(self):
        d = sample()
        d.pop("historical_v17_gate_target")
        with self.assertRaises(module.InvalidSnapshot):
            module.triage(d)
        d = sample()
        d["private_volume_path"] = "/data/private-file"
        with self.assertRaises(module.InvalidSnapshot):
            module.triage(d)
        raw = SNAPSHOT.read_text("utf-8").replace('"schema":', '"schema":"fake","schema":', 1)
        with self.assertRaises(module.InvalidSnapshot):
            module.parse(raw.encode())

    def test_reject_oversize_invalid_json_and_nonfinite(self):
        for raw in (b"", b"x" * (module.MAX_BYTES + 1),
                    b'{"x": NaN}', b"\xff", b"[]", b"{bad"):
            with self.subTest(raw=raw[:20]):
                with self.assertRaises(module.InvalidSnapshot):
                    module.parse(raw)

    def test_cli_never_echoes_sensitive_filename_or_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "SECRET_OPERATOR_FILE.json"
            p.write_text(json.dumps(sample()), encoding="utf-8")
            ok = subprocess.run([sys.executable,str(SCRIPT),str(p)],
                                capture_output=True,text=True,timeout=10)
            self.assertEqual(ok.returncode,0,ok.stderr)
            report=json.loads(ok.stdout)
            self.assertEqual(report["status"],
                             "HOLD_INDEPENDENT_RUNTIME_AND_RECOVERY_EVIDENCE")
            self.assertNotIn("SECRET_OPERATOR_FILE",ok.stdout)
            bad=sample()
            bad["private_secret"]="PROTECTED_CONTENT"
            p.write_text(json.dumps(bad),encoding="utf-8")
            result=subprocess.run([sys.executable,str(SCRIPT),str(p)],
                                  capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,2)
            self.assertNotIn("PROTECTED_CONTENT",result.stdout+result.stderr)
            self.assertNotIn("SECRET_OPERATOR_FILE",result.stdout+result.stderr)
            self.assertNotIn("PASS",result.stdout)

    def test_symlinked_file_not_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "alias.json"
            p.symlink_to(SNAPSHOT)
            r=subprocess.run([sys.executable,str(SCRIPT),str(p)],
                             capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,2)

    def test_metadata_snapshot_tracks_reviewed_public_commit_ids(self):
        record = sample()
        self.assertEqual(record["railway_live_source"],
                         "9abbc067aad3ebbb0956432cf6682d2ea70e2824")
        self.assertEqual(record["historical_v17_gate_target"],
                         "3c0977f4c7fc9fb5e9a78bdb1eeb581cb3cb4959")
        self.assertEqual(record["github_main_at_observation"],
                         "4d97bafd840165469270e724195fd16ce8e33a13")
        self.assertEqual(record["staged_change_count"],2)
        self.assertEqual(record["live_healthcheck_path"],"/")
        self.assertEqual(record["staged_healthcheck_path"],"/readyz")


if __name__ == "__main__":
    unittest.main(verbosity=2)
