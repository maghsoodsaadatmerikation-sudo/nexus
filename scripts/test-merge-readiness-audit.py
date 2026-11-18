#!/usr/bin/env python3
"""Hostile, no-network regression tests for the informational merge-readiness audit."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("nexus_merge_readiness", HERE / "merge-readiness-audit.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

SHA = "c" * 40
MAIN_SHA = "d" * 40
RID = gate.REPO_ID
PR = 288


def payload():
    rules = {"id": 20870033, "enforcement": "active", "target": "branch",
             "source": gate.REPO,
             "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
             "rules": [
                 {"type": "deletion"},
                 {"type": "pull_request", "parameters": {
                     "required_approving_review_count": 0}},
                 {"type": "required_status_checks", "parameters": {
                     "strict_required_status_checks_policy": False,
                     "required_status_checks": [
                         {"context": "readonly-verification", "integration_id": 15368}]
                 }}
             ]}
    runs = []
    for i, (name, path) in enumerate(gate.REQUIRED.items(), start=1000):
        runs.append({
            "id": i, "name": name, "path": path, "event": "pull_request",
            "head_sha": SHA, "status": "completed", "conclusion": "success",
            "run_attempt": 1,
            "repository": {"id": RID}, "head_repository": {"id": RID},
            "pull_requests": [{"number": PR}],
        })
    return {
        "repo": {"id": RID, "full_name": gate.REPO, "default_branch": "main",
                 "archived": False, "disabled": False},
        "main": {"name": "main", "commit": {"sha": MAIN_SHA}},
        "pr": {"number": PR, "state": "open", "merged": False,
               "draft": True, "mergeable": True,
               "head": {"sha": SHA, "repo": {"id": RID}},
               "base": {"ref": "main", "sha": MAIN_SHA, "repo": {"id": RID}}},
        "ruleset": rules,
        "runs": {"workflow_runs": runs},
        "expected_pr": PR, "expected_sha": SHA,
    }


class AuditTests(unittest.TestCase):
    def deny(self, modify, reason=None):
        f = copy.deepcopy(payload())
        modify(f)
        with self.assertRaises(gate.AuditError) as ctx:
            gate.assess(**f)
        if reason is not None:
            self.assertIn(reason, str(ctx.exception))

    def test_realistic_snapshot_is_green_but_not_authorized(self):
        x = gate.assess(**payload())
        self.assertTrue(x["ci_snapshot_green"])
        self.assertTrue(x["required_readonly_check_enforced"])
        self.assertFalse(x["strict_base_freshness_enforced"])
        self.assertIn("DRAFT_PR", x["blockers"])
        self.assertIn("INDEPENDENT_APPROVAL_NOT_REQUIRED_BY_RULESET", x["blockers"])
        self.assertIn("STRICT_BASE_FRESHNESS_NOT_ENFORCED", x["blockers"])
        self.assertEqual(x["review_state"], "HOLD")
        self.assertIs(x["merge_authorized"], False)
        self.assertIs(x["release_authorized"], False)

    def test_even_nondraft_and_review_rule_cannot_self_authorize(self):
        f = payload()
        f["pr"]["draft"] = False
        f["ruleset"]["rules"][1]["parameters"]["required_approving_review_count"] = 1
        f["ruleset"]["rules"][2]["parameters"]["strict_required_status_checks_policy"] = True
        x = gate.assess(**f)
        self.assertTrue(x["ci_snapshot_green"])
        self.assertNotIn("DRAFT_PR", x["blockers"])
        self.assertFalse(x["merge_authorized"])
        self.assertIn("OWNER_REVIEW_AND_EXPLICIT_MERGE_DECISION_REQUIRED", x["blockers"])

    def test_wrong_repo_identity_denied(self):
        self.deny(lambda f: f["repo"].update(id=999), "repository identity")

    def test_bad_main_response_denied(self):
        self.deny(lambda f: f["main"]["commit"].update(sha="not sha"), "main branch")

    def test_pr_head_sha_changed_denied(self):
        self.deny(lambda f: f["pr"]["head"].update(sha="e"*40), "stale")

    def test_base_branch_advanced_denied(self):
        self.deny(lambda f: f["main"]["commit"].update(sha="e"*40), "stale")

    def test_pr_fork_denied(self):
        self.deny(lambda f: f["pr"]["head"]["repo"].update(id=999), "cross-repository")

    def test_closed_pr_denied(self):
        self.deny(lambda f: f["pr"].update(state="closed"), "closed")

    def test_ruleset_disabled_denied(self):
        self.deny(lambda f: f["ruleset"].update(enforcement="disabled"), "ruleset")

    def test_ruleset_scope_changed_denied(self):
        self.deny(lambda f: f["ruleset"]["conditions"]["ref_name"].update(include=["refs/heads/other"]),
                  "targets")

    def test_required_status_removed_denied(self):
        self.deny(lambda f: f["ruleset"]["rules"][2]["parameters"].update(required_status_checks=[]),
                  "readonly-verification")

    def test_required_status_integration_spoof_denied(self):
        self.deny(lambda f: f["ruleset"]["rules"][2]["parameters"]["required_status_checks"][0].update(
            integration_id=999), "readonly-verification")

    def test_no_required_approvals_is_reported_not_hidden(self):
        x = gate.assess(**payload())
        self.assertEqual(x["required_approvals"], 0)

    def test_missing_ci_workflow_blocks_not_crashes(self):
        f = payload()
        f["runs"]["workflow_runs"].pop()
        x = gate.assess(**f)
        self.assertFalse(x["ci_snapshot_green"])
        self.assertIn("EXPECTED_CI_NOT_FULLY_VERIFIED", x["blockers"])

    def test_successful_wrong_sha_does_not_count(self):
        f = payload()
        f["runs"]["workflow_runs"][0]["head_sha"] = "e"*40
        self.assertFalse(gate.assess(**f)["ci_snapshot_green"])

    def test_successful_wrong_path_does_not_count(self):
        f = payload()
        f["runs"]["workflow_runs"][0]["path"] = ".github/workflows/fake.yml"
        self.assertFalse(gate.assess(**f)["ci_snapshot_green"])

    def test_successful_fork_run_does_not_count(self):
        f = payload()
        f["runs"]["workflow_runs"][0]["head_repository"]["id"] = 999
        self.assertFalse(gate.assess(**f)["ci_snapshot_green"])

    def test_successful_unrelated_pr_does_not_count(self):
        f = payload()
        f["runs"]["workflow_runs"][0]["pull_requests"] = [{"number": 287}]
        self.assertFalse(gate.assess(**f)["ci_snapshot_green"])

    def test_null_pr_associations_does_not_crash(self):
        f = payload()
        f["runs"]["workflow_runs"][0]["pull_requests"] = None
        self.assertFalse(gate.assess(**f)["ci_snapshot_green"])

    def test_rerun_does_not_count(self):
        f = payload()
        f["runs"]["workflow_runs"][0]["run_attempt"] = 2
        self.assertFalse(gate.assess(**f)["ci_snapshot_green"])

    def test_later_failed_matching_run_blocks(self):
        f = payload()
        second = copy.deepcopy(f["runs"]["workflow_runs"][0])
        second.update(id=8000, conclusion="failure")
        f["runs"]["workflow_runs"].append(second)
        self.assertFalse(gate.assess(**f)["ci_snapshot_green"])

    def test_duplicate_json_denied(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "dup.json"
            p.write_text('{"id": 1, "id": 2}')
            with self.assertRaises(gate.AuditError):
                gate.read_json(p)

    def test_malformed_json_denied(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.json"
            p.write_text('{"id": NaN}')
            with self.assertRaises(gate.AuditError):
                gate.read_json(p)

    def test_never_perform_merge_or_network_calls(self):
        src = (HERE / "merge-readiness-audit.py").read_text()
        for word in ("subprocess.", "urllib.request", "requests.get(", "gh pr merge",
                     "gh release", "os.system", "exec(", "merge_authorized\": True"):
            self.assertNotIn(word, src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
