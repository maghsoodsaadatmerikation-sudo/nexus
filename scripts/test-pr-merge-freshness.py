#!/usr/bin/env python3
"""Adversarial fixture tests for exact PR base and protected-ruleset checks."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

SCRIPT = Path(__file__).with_name("verify-pr-merge-freshness.py")
spec = importlib.util.spec_from_file_location("nexus_pr_freshness", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

SHA = "a" * 40
OTHER_SHA = "b" * 40


def good_ruleset():
    return {
        "id": gate.RULESET_ID,
        "source": gate.REPOSITORY,
        "target": "branch",
        "enforcement": "active",
        "conditions": {
            "ref_name": {
                "include": ["~DEFAULT_BRANCH"],
                "exclude": [],
            },
        },
        "bypass_actors": [],
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {"type": "pull_request", "parameters": {"required_approving_review_count": 0}},
            {"type": "required_status_checks", "parameters": {
                "strict_required_status_checks_policy": True,
                "required_status_checks": [
                    {"context": gate.REQUIRED_CHECK, "integration_id": 15368},
                ],
            }},
        ],
    }


def good_branch():
    return {"ref": "refs/heads/main", "object": {"sha": SHA, "type": "commit"}}


class ProtectionTests(unittest.TestCase):
    def setUp(self):
        self.ruleset = good_ruleset()
        self.branch = good_branch()

    def check(self):
        return gate.validate(self.ruleset, self.branch, SHA)

    def test_valid_exact_base_and_strict_ruleset_passes(self):
        report = self.check()
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["observed_main_sha"], SHA)
        self.assertFalse(report["production_release_authorized"])

    def test_current_real_ruleset_setting_is_blocked(self):
        self.ruleset["rules"][-1]["parameters"]["strict_required_status_checks_policy"] = False
        with self.assertRaisesRegex(gate.Hold, "not strict"):
            self.check()

    def test_base_drift_is_blocked(self):
        self.branch["object"]["sha"] = OTHER_SHA
        with self.assertRaisesRegex(gate.Hold, "base is stale"):
            self.check()

    def test_missing_pr_gate_is_blocked(self):
        self.ruleset["rules"] = [rule for rule in self.ruleset["rules"]
                                 if rule["type"] != "pull_request"]
        with self.assertRaises(gate.Hold):
            self.check()

    def test_missing_required_verification_is_blocked(self):
        self.ruleset["rules"][-1]["parameters"]["required_status_checks"] = [
            {"context": "other", "integration_id": 15368},
        ]
        with self.assertRaises(gate.Hold):
            self.check()

    def test_untrusted_check_without_integration_identity_is_blocked(self):
        self.ruleset["rules"][-1]["parameters"]["required_status_checks"] = [
            {"context": gate.REQUIRED_CHECK},
        ]
        with self.assertRaises(gate.Hold):
            self.check()

    def test_bypass_actor_is_blocked(self):
        self.ruleset["bypass_actors"] = [{"actor_id": 1}]
        with self.assertRaises(gate.Hold):
            self.check()

    def test_inactive_or_wrong_scoped_ruleset_is_blocked(self):
        for path, value in (("enforcement", "disabled"),
                            ("source", "someone/else"),
                            ("target", "tag"),
                            ("id", 1)):
            with self.subTest(path=path):
                mutated = deepcopy(good_ruleset())
                mutated[path] = value
                with self.assertRaises(gate.Hold):
                    gate.validate(mutated, self.branch, SHA)

    def test_default_branch_exclusion_is_blocked(self):
        self.ruleset["conditions"]["ref_name"]["exclude"] = ["refs/heads/main"]
        with self.assertRaises(gate.Hold):
            self.check()

    def test_force_push_and_deletion_require_separate_rules(self):
        for rule_type in ("deletion", "non_fast_forward"):
            with self.subTest(rule_type=rule_type):
                mutated = deepcopy(good_ruleset())
                mutated["rules"] = [rule for rule in mutated["rules"]
                                    if rule["type"] != rule_type]
                with self.assertRaises(gate.Hold):
                    gate.validate(mutated, self.branch, SHA)

    def test_duplicate_status_check_rule_is_blocked(self):
        self.ruleset["rules"].append(deepcopy(self.ruleset["rules"][-1]))
        with self.assertRaises(gate.Hold):
            self.check()

    def test_malformed_sha_and_branch_object_are_blocked(self):
        for sha in ("", "b" * 39, "z" * 40, "B" * 40):
            with self.subTest(sha=sha):
                with self.assertRaises(gate.Hold):
                    gate.validate(self.ruleset, self.branch, sha)
        self.branch["object"]["type"] = "tag"
        with self.assertRaises(gate.Hold):
            self.check()

    def test_wrong_repository_context_is_blocked(self):
        with self.assertRaises(gate.Hold):
            gate.validate(self.ruleset, self.branch, SHA, "other/repo")

    def test_duplicate_json_keys_are_rejected(self):
        with self.assertRaises(gate.Hold):
            json.loads('{"status":"ready","status":"false"}',
                       object_pairs_hook=gate.no_duplicates)

    def test_optimized_python_cannot_suppress_live_failure(self):
        # No GitHub network access is required: an invalid context fails first.
        result = subprocess.run(
            [sys.executable, "-O", str(SCRIPT)],
            env={"GITHUB_EVENT_NAME": "pull_request",
                 "GITHUB_REPOSITORY": gate.REPOSITORY,
                 "NEXUS_PR_BASE_REF": "main",
                 "NEXUS_PR_BASE_SHA": "wrong"},
            capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BLOCKED", result.stderr)


if __name__ == "__main__":
    unittest.main()
