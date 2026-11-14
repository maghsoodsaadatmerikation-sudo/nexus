#!/usr/bin/env python3
"""Synthetic-only adversarial tests for the no-credential production freeze gate."""
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("production-freeze-preflight.py")
spec = importlib.util.spec_from_file_location("production_freeze_preflight", SCRIPT)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

SHA = "b" * 40
NOW = datetime(2026, 11, 14, 10, 0, 0, tzinfo=timezone.utc)


def sample():
    return {
        "schema": guard.SCHEMA,
        "observed_at_utc": "2026-11-14T09:50:00Z",
        "render": {
            "id": guard.RENDER_SERVICE, "repo": "https://github.com/" + guard.REPO,
            "branch": "main", "type": "web_service",
            "serviceDetails": {"env": "docker"},
            "autoDeploy": "no", "autoDeployTrigger": "off"
        },
        "github_main_ref": {
            "ref": "refs/heads/main", "object": {"sha": SHA, "type": "commit"}
        },
        "github_ruleset": {
            "id": guard.RULESET_ID, "source": guard.REPO, "target": "branch",
            "enforcement": "active",
            "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
            "bypass_actors": [], "current_user_can_bypass": "never",
            "rules": [
                {"type": "deletion"}, {"type": "non_fast_forward"},
                {"type": "pull_request", "parameters": {"required_approving_review_count": 0}},
                {"type": "required_status_checks", "parameters": {
                    "strict_required_status_checks_policy": True,
                    "do_not_enforce_on_create": False,
                    "required_status_checks": [{"context": guard.REQUIRED_CHECK, "integration_id": 15368}]
                }}
            ]
        }
    }


class FreezePreflightTests(unittest.TestCase):
    def result(self, doc=None, sha=SHA, now=NOW):
        return guard.assess(doc if doc is not None else sample(), sha, now=now)

    def test_consistent_synthetic_metadata_still_grants_no_authority(self):
        outcome = self.result()
        self.assertEqual(outcome["configuration_review"], "CONSISTENT_INPUT_ONLY")
        self.assertEqual(outcome["blockers"], [])
        for key in ("provider_identity_authenticated", "real_backup_inspected",
                    "independent_restore_verified", "merge_authorized",
                    "deployment_authorized", "release_seal_authorized"):
            self.assertIs(outcome[key], False)
        self.assertEqual(outcome["authority"], "none")

    def test_currently_observed_unfrozen_settings_remain_blocked(self):
        doc = sample()
        doc["render"].update(autoDeploy="yes", autoDeployTrigger="commit")
        next(r for r in doc["github_ruleset"]["rules"]
             if r["type"] == "required_status_checks")["parameters"]["strict_required_status_checks_policy"] = False
        result = self.result(doc)
        self.assertEqual(result["configuration_review"], "BLOCKED")
        self.assertIn("render_autodeploy_not_disabled", result["blockers"])
        self.assertIn("github_strict_required_checks_missing", result["blockers"])

    def test_each_autodeploy_field_must_confirm_freeze(self):
        for key, value in (("autoDeploy", "yes"),
                           ("autoDeploy", None),
                           ("autoDeployTrigger", "checksPass"),
                           ("autoDeployTrigger", None)):
            with self.subTest(field=key, value=value):
                doc = sample()
                doc["render"][key] = value
                self.assertIn("render_autodeploy_not_disabled", self.result(doc)["blockers"])

    def test_wrong_render_service_source_branch_or_runtime_fails(self):
        mutations = (
            ("id", "srv-foreign", "render_service_identity_unverified"),
            ("repo", "https://github.com/other/nexus", "render_source_configuration_mismatch"),
            ("branch", "some-feature", "render_source_configuration_mismatch"),
            ("type", "static_site", "render_source_configuration_mismatch"),
            ("serviceDetails", {}, "render_source_configuration_mismatch"),
        )
        for field, value, expected in mutations:
            with self.subTest(field=field):
                doc = sample()
                doc["render"][field] = value
                self.assertIn(expected, self.result(doc)["blockers"])

    def test_unknown_and_unprotected_main_ref_fail(self):
        for change in (
            {"ref": "refs/heads/staging"}, {"object": {"sha": "c" * 40, "type": "commit"}},
            {"object": {"sha": SHA, "type": "tag"}}
        ):
            with self.subTest(change=change):
                doc = sample()
                doc["github_main_ref"].update(change)
                self.assertIn("github_main_sha_unverified", self.result(doc)["blockers"])
        self.assertIn("github_main_sha_unverified", self.result(sample(), "c" * 40)["blockers"])

    def test_ruleset_missing_or_wrong_identity_fails(self):
        for field, value in (("id", True), ("id", 999),
                             ("source", "elsewhere"), ("enforcement", "disabled"),
                             ("target", "tag")):
            with self.subTest(field=field):
                doc = sample()
                doc["github_ruleset"][field] = value
                self.assertIn("github_ruleset_identity_unverified", self.result(doc)["blockers"])

    def test_default_branch_coverage_mandatory(self):
        for ref in (
            {"include": ["refs/heads/release"], "exclude": []},
            {"include": ["~DEFAULT_BRANCH"], "exclude": ["refs/heads/main"]},
            None,
        ):
            with self.subTest(ref=ref):
                doc = sample()
                doc["github_ruleset"]["conditions"] = {"ref_name": ref}
                self.assertIn("github_main_not_covered_by_ruleset", self.result(doc)["blockers"])

    def test_ruleset_cannot_skip_pr_or_history_protections(self):
        for kind in ("deletion", "non_fast_forward", "pull_request", "required_status_checks"):
            doc = sample()
            doc["github_ruleset"]["rules"] = [
                r for r in doc["github_ruleset"]["rules"] if r["type"] != kind
            ]
            self.assertIn("github_required_rules_unverified", self.result(doc)["blockers"])

    def test_strict_check_must_be_exact_and_required(self):
        changes = [
            {"strict_required_status_checks_policy": False},
            {"strict_required_status_checks_policy": "true"},
            {"do_not_enforce_on_create": True},
            {"required_status_checks": [{"context": "some-other-check"}]},
            {"required_status_checks": []},
        ]
        for change in changes:
            with self.subTest(change=change):
                doc = sample()
                next(r for r in doc["github_ruleset"]["rules"] if
                     r["type"] == "required_status_checks")["parameters"].update(change)
                self.assertIn("github_strict_required_checks_missing", self.result(doc)["blockers"])

    def test_redacted_bypass_scope_must_be_blocked(self):
        for key, value in (("bypass_actors", None),
                           ("bypass_actors", [{"actor_id": 1}]),
                           ("current_user_can_bypass", "always")):
            doc = sample()
            doc["github_ruleset"][key] = value
            self.assertIn("github_bypass_scope_unverified", self.result(doc)["blockers"])

    def test_stale_future_or_invalid_timestamp_fail(self):
        for date in ("2026-11-14T09:29:59Z", "2026-11-14T10:02:01Z",
                     "2026-11-14T99:00:00Z", "2026-11-14T10:00:00+01:00",
                     None):
            with self.subTest(date=date):
                doc = sample()
                doc["observed_at_utc"] = date
                self.assertIn("provider_observation_not_fresh", self.result(doc)["blockers"])

    def test_invalid_observation_envelope_blocks_instead_of_pass(self):
        for change in ({"schema": "other"}, {"extra": "untrusted"}, {"render": "invalid"}):
            doc = sample()
            doc.update(change)
            if "render" in change:
                self.assertIn("render_service_identity_unverified", self.result(doc)["blockers"])
            else:
                with self.assertRaises(guard.InvalidEvidence):
                    self.result(doc)
        with self.assertRaises(guard.InvalidEvidence):
            self.result(sample(), "short")

    def test_input_file_rejects_duplicate_json_keys_and_symlinks(self):
        with tempfile.TemporaryDirectory() as d:
            raw = Path(d) / "snapshot.json"
            raw.write_text('{"schema":"first","schema":"second"}')
            with self.assertRaises(guard.InvalidEvidence):
                guard.read_snapshot(raw)
            raw.write_text('{"value":NaN}')
            with self.assertRaises(guard.InvalidEvidence):
                guard.read_snapshot(raw)
            raw.write_text(json.dumps(sample()))
            self.assertEqual(guard.read_snapshot(raw)["schema"], guard.SCHEMA)
            alias = Path(d) / "alias.json"
            alias.symlink_to(raw)
            with self.assertRaises(OSError):
                guard.read_snapshot(alias)

    def test_file_size_and_hardlinks_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "snapshot.json"
            path.write_bytes(b"x" * (guard.MAX_BYTES + 1))
            with self.assertRaises(guard.InvalidEvidence):
                guard.read_snapshot(path)
            path.write_text(json.dumps(sample()))
            alias = Path(d) / "hardlink"
            alias.hardlink_to(path)
            with self.assertRaises(guard.InvalidEvidence):
                guard.read_snapshot(path)

    def test_cli_never_echoes_sensitive_input_and_never_authorizes(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "private-secret-snapshot.json"
            doc = sample()
            doc["observed_at_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            doc["extra-secret"] = "SENSITIVE-SENTINEL"
            path.write_text(json.dumps(doc))
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(path), "--expected-main-sha", SHA],
                text=True, capture_output=True, timeout=5)
            self.assertEqual(proc.returncode, 2)
            self.assertNotIn("SENSITIVE-SENTINEL", proc.stdout + proc.stderr)
            self.assertNotIn(str(path), proc.stdout + proc.stderr)
            del doc["extra-secret"]
            path.write_text(json.dumps(doc))
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(path), "--expected-main-sha", SHA],
                text=True, capture_output=True, timeout=5)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            outcome = json.loads(proc.stdout)
            self.assertEqual(outcome["configuration_review"], "CONSISTENT_INPUT_ONLY")
            self.assertIs(outcome["deployment_authorized"], False)


if __name__ == "__main__":
    unittest.main()
