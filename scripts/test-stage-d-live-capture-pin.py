#!/usr/bin/env python3
"""Synthetic-only exact manual provider-identity preflight regression tests.

Runs the actual first Bash preflight block from the protected workflow. No
Railway credentials or provider calls, real Volume bytes or production writes.
"""
import os
from pathlib import Path
import subprocess
import unittest

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github/workflows/stage-d-encrypted-volume-capture.yml"
ORIGINAL_VOLUME = "cc47a350-6c7e-4487-89d9-c4b390f94884"
CURRENT_DEPLOYMENT = "32cdcb2b-c03c-4a6f-b028-27a9977717ce"
CURRENT_RUNTIME = "9abbc067aad3ebbb0956432cf6682d2ea70e2824"
OLD_DEPLOYMENT = "db2fd959-918e-49d5-b077-1ac74fac9a82"
OLD_RUNTIME = "3c0977f4c7fc9fb5e9a78bdb1eeb581cb3cb4959"

FIRST = "      - name: Fail-closed target and recipient check (no secret)"
SECOND = "      - name: Fail-closed selected Railway credential scope BEFORE CLI download"
CAPTURE_STEP = "      - name: Exact-target READ-ONLY download + private quarantine rehearsal"
ENCRYPT_STEP = "      - name: Encrypt only three validated private evidence files"


def bash_first_step():
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert raw.count(FIRST) == raw.count(SECOND) == raw.count(CAPTURE_STEP) == 1
    part = raw.split(FIRST, 1)[1].split(SECOND, 1)[0]
    assert "        run: |\n" in part
    shell = part.split("        run: |\n", 1)[1].splitlines()
    assert all(not line or line.startswith("          ") for line in shell)
    return raw, "\n".join(line[10:] if line else "" for line in shell) + "\n"


class LivePinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow, cls.script = bash_first_step()

    def check(self, *, volume=ORIGINAL_VOLUME, deployment=CURRENT_DEPLOYMENT,
              runtime=CURRENT_RUNTIME, key_ack="I VERIFIED MY STAGE D RECOVERY KEY LOCALLY"):
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/tmp",
               "CONFIRM_VOLUME": volume, "CONFIRM_DEPLOYMENT": deployment,
               "CONFIRM_RUNTIME": runtime, "KEY_ACK": key_ack}
        return subprocess.run(["bash", "-c", self.script], cwd=REPO,
                              env=env, capture_output=True, text=True, timeout=5)

    def test_current_exact_values_pass_synthetic_only_no_provider(self):
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("RAILWAY_TOKEN", result.stderr)

    def test_removed_and_other_deployments_block(self):
        for val in (OLD_DEPLOYMENT, "", "0" * 36, CURRENT_DEPLOYMENT + " "):
            with self.subTest(value=val):
                r = self.check(deployment=val)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("BLOCKED", r.stdout)

    def test_legacy_main_and_malformed_sha_block(self):
        for val in (OLD_RUNTIME, "", CURRENT_RUNTIME.upper(), "0" * 40):
            with self.subTest(value=val):
                r = self.check(runtime=val)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("BLOCKED", r.stdout)

    def test_wrong_volume_and_unproven_key_block(self):
        self.assertNotEqual(self.check(volume="0" * 36).returncode, 0)
        self.assertNotEqual(self.check(key_ack="I HAVE A KEY").returncode, 0)

    def test_provider_identity_bound_in_capture_not_just_bash(self):
        src = (REPO / "scripts/capture-railway-volume-readonly.py").read_text()
        self.assertIn('DEPLOYMENT = "' + CURRENT_DEPLOYMENT + '"', src)
        self.assertIn('RUNTIME = "' + CURRENT_RUNTIME + '"', src)
        self.assertIn('getattr(args, "confirm_deployment", None) == DEPLOYMENT', src)
        self.assertIn('getattr(args, "confirm_runtime", None) == RUNTIME', src)
        capture = self.workflow.split(CAPTURE_STEP, 1)[1].split(ENCRYPT_STEP, 1)[0]
        self.assertIn("--confirm-deployment", capture)
        self.assertIn("--confirm-runtime", capture)
        self.assertIn("inputs.confirm_deployment", capture)
        self.assertIn("inputs.confirm_runtime", capture)
        self.assertIn("        required: true", self.workflow)
        self.assertIn("  workflow_dispatch:", self.workflow)
        self.assertNotIn("  push:", self.workflow)
        self.assertNotIn("  pull_request:", self.workflow)
        self.assertLess(self.workflow.index(FIRST), self.workflow.index(SECOND))
        self.assertLess(self.workflow.index(SECOND), self.workflow.index(CAPTURE_STEP))


if __name__ == "__main__":
    unittest.main(verbosity=2)
