#!/usr/bin/env python3
"""No-provider, synthetic verification of real manual workflow credential guard.

Exercises the ACTUAL inline bash preflight, extracted from the workflow,
with dummy token presence only. No GitHub secrets or Railway API are used.
"""
import os
from pathlib import Path
import subprocess
import unittest

HERE = Path(__file__).resolve().parent
WORKFLOW = HERE.parent / ".github/workflows/stage-d-encrypted-volume-capture.yml"
PREFLIGHT_NAME = "      - name: Fail-closed selected Railway credential scope BEFORE CLI download"
CLI_NAME = "      - name: Download genuine pinned Railway CLI (no Railway credential)"
EXECUTE_NAME = "      - name: Exact-target READ-ONLY download + private quarantine rehearsal"
ENCRYPT_NAME = "      - name: Encrypt only three validated private evidence files"


def workflow_sections():
    body = WORKFLOW.read_text(encoding="utf-8")
    assert body.count(PREFLIGHT_NAME) == 1
    assert body.count(CLI_NAME) == 1
    assert body.count(EXECUTE_NAME) == 1
    assert body.count(ENCRYPT_NAME) == 1
    preflight = body.split(PREFLIGHT_NAME, 1)[1].split(CLI_NAME, 1)[0]
    download = body.split(EXECUTE_NAME, 1)[1].split(ENCRYPT_NAME, 1)[0]
    assert "        run: |\n" in preflight
    script = preflight.split("        run: |\n", 1)[1]
    lines = script.splitlines()
    assert lines and all(line.startswith("          ") or not line for line in lines)
    return body, preflight, download, "\n".join(
        line[10:] if line else "" for line in lines) + "\n"


class CredentialSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (cls.workflow, cls.preflight,
         cls.download, cls.script) = workflow_sections()

    def guard(self, scope, ack="", project="", workspace=""):
        environment = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": "/tmp",
            "SCOPE": scope,
            "WORKSPACE_ACK": ack,
            "PROJECT_TOKEN": project,
            "WORKSPACE_TOKEN": workspace,
        }
        return subprocess.run(
            ["bash", "-c", self.script],
            input="", text=True, capture_output=True, env=environment, timeout=5)

    def assert_refusal(self, scope, ack="", project="", workspace=""):
        result = self.guard(scope, ack, project, workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("SYNTHETIC_PROJECT_SECRET", result.stdout + result.stderr)
        self.assertNotIn("SYNTHETIC_WORKSPACE_SECRET", result.stdout + result.stderr)

    def test_project_scope_with_only_project_secret_is_allowed(self):
        r = self.guard("project", project="SYNTHETIC_PROJECT_SECRET")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("SYNTHETIC_PROJECT_SECRET", r.stdout + r.stderr)

    def test_workspace_scope_requires_explicit_ack_and_its_own_secret(self):
        r = self.guard("workspace", ack="I ACCEPT WORKSPACE TOKEN SCOPE",
                       workspace="SYNTHETIC_WORKSPACE_SECRET")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("SYNTHETIC_WORKSPACE_SECRET", r.stdout + r.stderr)

    def test_no_project_secret_refused_before_any_cli_download(self):
        self.assert_refusal("project")

    def test_project_scope_with_workspace_token_refused(self):
        self.assert_refusal("project", workspace="SYNTHETIC_WORKSPACE_SECRET")

    def test_both_tokens_in_project_scope_refused(self):
        self.assert_refusal("project", project="SYNTHETIC_PROJECT_SECRET",
                            workspace="SYNTHETIC_WORKSPACE_SECRET")

    def test_project_scope_with_workspace_ack_refused(self):
        self.assert_refusal("project", ack="I ACCEPT WORKSPACE TOKEN SCOPE",
                            project="SYNTHETIC_PROJECT_SECRET")

    def test_workspace_scope_without_ack_refused(self):
        self.assert_refusal("workspace", workspace="SYNTHETIC_WORKSPACE_SECRET")

    def test_workspace_scope_with_wrong_ack_refused(self):
        self.assert_refusal("workspace", ack="yes",
                            workspace="SYNTHETIC_WORKSPACE_SECRET")

    def test_workspace_scope_with_project_only_refused(self):
        self.assert_refusal("workspace", ack="I ACCEPT WORKSPACE TOKEN SCOPE",
                            project="SYNTHETIC_PROJECT_SECRET")

    def test_workspace_scope_with_both_tokens_refused(self):
        self.assert_refusal("workspace", ack="I ACCEPT WORKSPACE TOKEN SCOPE",
                            project="SYNTHETIC_PROJECT_SECRET",
                            workspace="SYNTHETIC_WORKSPACE_SECRET")

    def test_unknown_scope_refused(self):
        self.assert_refusal("other", project="SYNTHETIC_PROJECT_SECRET")

    def test_manual_main_only_and_credential_selection_precedes_network(self):
        s = self.workflow
        self.assertIn("workflow_dispatch:", s)
        self.assertNotIn("  push:", s)
        self.assertNotIn("  pull_request:", s)
        self.assertIn("github.ref == 'refs/heads/main'", s)
        self.assertTrue(s.index("      - name: Fail-closed target and recipient check") <
                        s.index(PREFLIGHT_NAME) < s.index(CLI_NAME) <
                        s.index(EXECUTE_NAME) < s.index(ENCRYPT_NAME))
        self.assertIn("type: choice", s)
        self.assertIn("default: project", s)
        self.assertIn("confirm_workspace_scope:", s)
        self.assertIn("I ACCEPT WORKSPACE TOKEN SCOPE", s)

    def test_each_secret_is_bound_only_to_exact_explicit_selected_scope(self):
        project = "inputs.credential_scope == 'project' && secrets.NEXUS_STAGE_D_RAILWAY_TOKEN || ''"
        workspace = "inputs.credential_scope == 'workspace' && secrets.NEXUS_STAGE_D_RAILWAY_WORKSPACE_API_TOKEN || ''"
        self.assertEqual(self.preflight.count(project), 1)
        self.assertEqual(self.preflight.count(workspace), 1)
        self.assertEqual(self.download.count(project), 1)
        self.assertEqual(self.download.count(workspace), 1)
        self.assertNotIn("secrets.NEXUS_STAGE_D_RAILWAY_WORKSPACE_API_TOKEN",
                         self.workflow.split(ENCRYPT_NAME)[1])
        self.assertNotIn("secrets.NEXUS_STAGE_D_RAILWAY_TOKEN",
                         self.workflow.split(ENCRYPT_NAME)[1])
        self.assertIn("python3 scripts/capture-railway-volume-readonly.py",
                      self.download)
        self.assertIn("--execute", self.download)
        for forbidden in ("railway redeploy", "railway up", "railway volume delete",
                          "railway volume detach", "railway volume files upload"):
            self.assertNotIn(forbidden, self.download)

if __name__ == "__main__":
    unittest.main(verbosity=2)
