#!/usr/bin/env python3
"""Exercise actual manual workflow preflight with synthetic token scopes only."""
import os
from pathlib import Path
import subprocess
import textwrap
import unittest

WORKFLOW = Path(__file__).resolve().parent.parent / ".github/workflows/stage-d-encrypted-volume-capture.yml"
STEP = "Fail-closed selected Railway credential scope BEFORE CLI download"

def workflow():
    return WORKFLOW.read_text(encoding="utf-8")

def shell():
    text = workflow()
    marker = "      - name: " + STEP + "\n"
    assert text.count(marker) == 1
    step = text.split(marker, 1)[1].split("      - name: ", 1)[0]
    return textwrap.dedent(step.split("        run: |\n", 1)[1])

def simulate(scope, ack="", project="", workspace=""):
    environment = {
        "PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/tmp",
        "SCOPE": scope, "WORKSPACE_ACK": ack,
        "PROJECT_TOKEN": project if scope == "project" else "",
        "WORKSPACE_TOKEN": workspace if scope == "workspace" else "",
    }
    return subprocess.run(["bash", "-e"], input=shell(), capture_output=True,
                          text=True, env=environment, timeout=5)

class CredentialScopeTests(unittest.TestCase):
    def test_project_secret_only_accept(self):
        result = simulate("project", project="FAKE_PROJECT_SECRET")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_workspace_secret_requires_explicit_accept(self):
        result = simulate("workspace", "I ACCEPT WORKSPACE TOKEN SCOPE",
                          workspace="FAKE_WORKSPACE_SECRET")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_no_project_secret_denied(self):
        self.assertNotEqual(simulate("project").returncode, 0)

    def test_no_workspace_secret_denied(self):
        self.assertNotEqual(simulate(
            "workspace", "I ACCEPT WORKSPACE TOKEN SCOPE").returncode, 0)

    def test_workspace_secret_no_project_fallback(self):
        self.assertNotEqual(simulate(
            "project", workspace="FAKE_WORKSPACE_SECRET").returncode, 0)

    def test_project_secret_no_workspace_fallback(self):
        self.assertNotEqual(simulate(
            "workspace", "I ACCEPT WORKSPACE TOKEN SCOPE",
            project="FAKE_PROJECT_SECRET").returncode, 0)

    def test_workspace_requires_exact_ack_case(self):
        for value in ("", "yes", "I ACCEPT", "i accept workspace token scope",
                      "I ACCEPT WORKSPACE TOKEN SCOPE ", "I ACCEPT WORKSPACE TOKEN SCOPE\nBAD"):
            with self.subTest(value=value):
                self.assertNotEqual(simulate(
                    "workspace", value, workspace="FAKE_WORKSPACE_SECRET").returncode, 0)

    def test_project_refuses_workspace_ack(self):
        self.assertNotEqual(simulate(
            "project", "I ACCEPT WORKSPACE TOKEN SCOPE",
            project="FAKE_PROJECT_SECRET").returncode, 0)

    def test_invalid_scope_denied(self):
        for scope in ("", "auto", "both", "account", "Project", "workspace\nproject"):
            with self.subTest(scope=scope):
                self.assertNotEqual(simulate(
                    scope, project="FAKE_PROJECT_SECRET",
                    workspace="FAKE_WORKSPACE_SECRET").returncode, 0)

    def test_workflow_manual_exact_scope_expressions(self):
        text = workflow()
        self.assertIn("  workflow_dispatch:\n", text)
        self.assertNotIn("  push:\n", text)
        self.assertNotIn("  schedule:\n", text)
        self.assertIn("    if: github.ref == 'refs/heads/main'", text)
        self.assertIn("        default: project", text)
        self.assertIn("          - project\n          - workspace", text)
        self.assertEqual(text.count("      - name: " + STEP), 1)
        self.assertLess(text.index(STEP), text.index("Download genuine pinned Railway CLI"))
        self.assertLess(text.index(STEP), text.index("Exact-target READ-ONLY download"))
        project = "inputs.credential_scope == 'project' && secrets.NEXUS_STAGE_D_RAILWAY_TOKEN || ''"
        workspace = "inputs.credential_scope == 'workspace' && secrets.NEXUS_STAGE_D_RAILWAY_WORKSPACE_API_TOKEN || ''"
        self.assertEqual(text.count(project), 2)
        self.assertEqual(text.count(workspace), 2)
        download = text.split(
            "      - name: Exact-target READ-ONLY download + private quarantine rehearsal\n",
            1)[1].split("      - name: ", 1)[0]
        self.assertIn("RAILWAY_TOKEN: " + "$" + "{{ " + project + " }}", download)
        self.assertIn("RAILWAY_API_TOKEN: " + "$" + "{{ " + workspace + " }}", download)
        self.assertIn("capture-railway-volume-readonly.py", download)
        self.assertIn("--execute", download)
        for bad in ("volume delete", "volume upload", "volume restore", "railway redeploy", "--overwrite"):
            self.assertNotIn(bad, download)

    def test_no_credentials_in_encryption_log_or_upload(self):
        text = workflow()
        for name in ("Encrypt only three validated private evidence files",
                     "Anchor non-secret ciphertext digest to this GitHub run log",
                     "Upload ciphertext and sanitized receipt ONLY"):
            with self.subTest(step=name):
                block = text.split("      - name: " + name + "\n", 1)[1].split("      - name: ", 1)[0]
                self.assertNotIn("secrets.", block)
                self.assertNotIn("NEXUS_STAGE_D_RAILWAY_WORKSPACE_API_TOKEN", block)
                self.assertNotIn("NEXUS_STAGE_D_RAILWAY_TOKEN", block)
        self.assertIn("if: always()", text)

    def test_preflight_never_echoes_secrets(self):
        script = shell()
        for bad in ("set -x", "printenv", "env |"):
            self.assertNotIn(bad, script)
        for scope, ack, project, workspace in (
            ("project", "", "FAKE_PROJECT_SECRET", ""),
            ("workspace", "I ACCEPT WORKSPACE TOKEN SCOPE", "", "FAKE_WORKSPACE_SECRET"),
            ("workspace", "", "", "FAKE_WORKSPACE_SECRET"),
            ("project", "I ACCEPT WORKSPACE TOKEN SCOPE", "FAKE_PROJECT_SECRET", ""),
        ):
            response = simulate(scope, ack, project, workspace)
            for secret in ("FAKE_PROJECT_SECRET", "FAKE_WORKSPACE_SECRET"):
                self.assertNotIn(secret, response.stdout + response.stderr)

if __name__ == "__main__":
    unittest.main(verbosity=2)
