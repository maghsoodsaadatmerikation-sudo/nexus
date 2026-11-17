#!/usr/bin/env python3
"""Disposable provider fixtures; no Railway credentials, deployments or real network."""
import copy
import datetime as dt
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("check-railway-cutover.py").resolve()
spec = importlib.util.spec_from_file_location("cutover", SCRIPT)
cutover = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cutover)

P = "2ac7887b-d67a-48be-8a7b-bd54092893ae"
S = "0032fc74-2c52-475d-b9df-9dca59237d93"
V = "cc47a350-6c7e-4487-89d9-c4b390f94884"
E = "56c4bc45-0e62-4aa9-832f-884bb1aa620c"
C = "a" * 40
D = "b" * 64
O = "https://nexus-stage-d-production.up.railway.app"
RUN = "fixture-run-id"
NOW = dt.datetime(2026, 11, 17, 10, tzinfo=dt.timezone.utc)


def fixture():
    observation = {path: {"method": "GET", "http_status": status}
                   for path, status in cutover.PUBLIC_PATHS.items()}
    return {
        "schema": cutover.SCHEMA, "captured_at_utc": NOW.isoformat(),
        "inventory": {"project": {"id": P}, "environment": {"name": "production", "id": E}, "staged": None},
        "service": {
            "service": {"id": S, "state": "live"}, "environment": {"id": E},
            "staged": None, "stagedChanges": [],
            "config": {"source": {"repo": "maghsoodsaadatmerikation-sudo/nexus",
                                  "branch": "main", "commitSha": C},
                       "deploy": {"healthcheckPath": "/readyz", "sleepApplication": False}},
            "variableNames": sorted(cutover.REQUIRED_ENV),
            "volumes": [{"id": V, "mountPath": "/data", "state": "live"}],
            "domains": {"serviceDomains": [{"domain": "nexus-stage-d-production.up.railway.app", "targetPort": 3000}]},
        },
        "health": {"environment": {"id": E},
                   "services": [{"serviceId": S, "state": "online",
                                  "activeDeployments": [{"id": RUN, "status": "SUCCESS"}],
                                  "issues": {"criticalCount": 0}, "recentFailures": 0}],
                   "pendingWork": []},
        "deployments": {"deployments": [{"id": RUN, "serviceId": S,
                                          "environmentId": E, "status": "SUCCESS",
                                          "meta": {"commitHash": C}}]},
        "public_observation": {"schema": "nexus.pilot.public-observation.v1",
                               "observed_at_utc": NOW.isoformat(), "origin": O,
                               "expected_source_tree_sha256": D, "observed_source_tree_sha256": D,
                               "candidate_digest_match": True, "observations": observation,
                               "public_checks": "SATISFIED", "blockers": [],
                               "promotion_ready": False, "production_mutation": False},
    }


def assess(value, always_on=False):
    return cutover.assessment(value, project_id=P, service_id=S, volume_id=V,
                             expected_commit=C, expected_digest=D,
                             expected_origin=O, now=NOW, always_on=always_on)


class CutoverTests(unittest.TestCase):
    def test_exact_success_is_still_not_release_approval(self):
        report = assess(fixture(), always_on=True)
        self.assertEqual(report["technical_preflight"], "SATISFIED")
        self.assertFalse(report["production_release_authorized"])
        self.assertFalse(report["provider_mutation"])
        self.assertEqual(report["independent_offsite_backup"], "NOT_ASSESSED")

    def test_staged_patch_blocks_even_without_destructive_changes(self):
        data = fixture()
        data["inventory"]["staged"] = {"status": "STAGED", "changeCount": 2}
        self.assertIn("environment_has_pending_changes", assess(data)["blockers"])

    def test_omitted_pending_state_is_not_treated_as_clean(self):
        for section, key in (("inventory", "staged"), ("service", "staged"),
                             ("service", "stagedChanges"), ("health", "pendingWork"),
                             ("public_observation", "blockers")):
            with self.subTest(section=section, key=key):
                data = fixture()
                data[section].pop(key)
                self.assertEqual(assess(data)["technical_preflight"], "BLOCKED")

    def test_source_pin_and_real_deployed_commit_both_required(self):
        for field in ("source", "deployment"):
            with self.subTest(field=field):
                data = fixture()
                if field == "source":
                    data["service"]["config"]["source"]["commitSha"] = "c" * 40
                else:
                    data["deployments"]["deployments"][0]["meta"]["commitHash"] = "c" * 40
                self.assertEqual(assess(data)["technical_preflight"], "BLOCKED")

    def test_mixed_environment_evidence_blocks(self):
        for changed in ("service", "health", "deployments"):
            with self.subTest(changed=changed):
                data = fixture()
                if changed == "deployments":
                    data["deployments"]["deployments"][0]["environmentId"] = "wrong"
                else:
                    data[changed]["environment"]["id"] = "wrong"
                self.assertEqual(assess(data)["technical_preflight"], "BLOCKED")

    def test_sleeping_service_and_on_demand_mode(self):
        data = fixture()
        data["health"]["services"][0]["state"] = "sleeping"
        self.assertIn("service_not_online", assess(data)["blockers"])
        data = fixture()
        data["service"]["config"]["deploy"]["sleepApplication"] = True
        self.assertEqual(assess(data)["technical_preflight"], "SATISFIED")
        self.assertIn("service_sleep_enabled", assess(data, always_on=True)["blockers"])

    def test_mount_and_secret_name_and_domain_required(self):
        for key in ("volumes", "variableNames", "domains"):
            with self.subTest(key=key):
                data = fixture()
                data["service"][key] = []
                self.assertEqual(assess(data)["technical_preflight"], "BLOCKED")

    def test_public_auth_exposure_and_bad_runtime_identity_block(self):
        data = fixture()
        data["public_observation"]["observations"]["/v1/workspaces"]["http_status"] = 200
        self.assertIn("public_get_boundary_failed:/v1/workspaces", assess(data)["blockers"])
        data = fixture()
        data["public_observation"]["observed_source_tree_sha256"] = "c" * 64
        self.assertIn("public_runtime_digest_mismatch", assess(data)["blockers"])

    def test_partial_missing_or_stale_input_fails_closed(self):
        for key in ("inventory", "service", "health", "deployments", "public_observation"):
            with self.subTest(key=key):
                data = fixture()
                data.pop(key)
                with self.assertRaises(cutover.InvalidInput):
                    assess(data)
        data = fixture()
        data["captured_at_utc"] = "2026-11-01T00:00:00Z"
        self.assertIn("snapshot_not_fresh", assess(data)["blockers"])

    def test_duplicate_key_symlink_and_oversize_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "snapshot.json"
            path.write_text('{"schema":"nexus.railway-cutover-input.v1","schema":"other"}')
            with self.assertRaises(cutover.InvalidInput):
                cutover.read_snapshot(path)
            path.write_bytes(b"x" * (cutover.MAX_BYTES + 1))
            with self.assertRaises(cutover.InvalidInput):
                cutover.read_snapshot(path)
            target = root / "link.json"
            target.symlink_to(path)
            with self.assertRaises(cutover.InvalidInput):
                cutover.read_snapshot(target)

    def test_cli_reports_blocked_without_emitting_secret_like_provider_values(self):
        data = fixture()
        data["inventory"]["staged"] = {"status": "STAGED"}
        data["service"]["private_field"] = "SENTINEL_DO_NOT_PRINT"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input.json"
            path.write_text(json.dumps(data))
            cmd = [sys.executable, str(SCRIPT), "--input", str(path), "--expected-project-id", P,
                   "--expected-service-id", S, "--expected-volume-id", V,
                   "--expected-commit", C, "--expected-digest", D, "--expected-origin", O]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertNotIn("SENTINEL_DO_NOT_PRINT", result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["technical_preflight"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
