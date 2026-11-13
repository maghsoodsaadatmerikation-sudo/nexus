#!/usr/bin/env python3
"""Adversarial regressions for the Render manual-deploy source boundary."""

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = Path(__file__).with_name("verify-render-manual-deployment.py")
spec = importlib.util.spec_from_file_location("nexus_render_hold", MODULE_PATH)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class ManualDeploymentBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.valid = (ROOT / "render.yaml").read_text(encoding="utf-8")

    def assert_rejected(self, changed):
        with self.assertRaises(ValueError):
            validator.verify(changed)

    def test_checked_in_blueprint_is_valid(self):
        validator.verify(self.valid)

    def test_auto_deployment_modes_are_rejected(self):
        for mode in ("checksPass", "commit", "yes", "true", "false"):
            with self.subTest(mode=mode):
                self.assert_rejected(self.valid.replace(
                    "autoDeployTrigger: 'off'", f"autoDeployTrigger: {mode}"))

    def test_omitted_deploy_guard_is_rejected(self):
        self.assert_rejected(self.valid.replace("    autoDeployTrigger: 'off'\n", ""))

    def test_duplicate_deploy_guard_is_rejected(self):
        self.assert_rejected(self.valid.replace(
            "    autoDeployTrigger: 'off'\n",
            "    autoDeployTrigger: 'off'\n    autoDeployTrigger: checksPass\n"))

    def test_legacy_auto_deploy_key_is_rejected(self):
        self.assert_rejected(self.valid.replace(
            "    autoDeployTrigger: 'off'\n",
            "    autoDeployTrigger: 'off'\n    autoDeploy: true\n"))

    def test_comment_with_fake_guard_is_rejected(self):
        self.assert_rejected(self.valid.replace(
            "    autoDeployTrigger: 'off'\n",
            "    autoDeployTrigger: checksPass\n    # autoDeployTrigger: 'off'\n"))

    def test_second_service_is_rejected(self):
        self.assert_rejected(self.valid + "  - type: web\n    autoDeployTrigger: 'off'\n")

    def test_unreviewed_service_override_is_rejected(self):
        self.assert_rejected(self.valid.replace(
            "    autoDeployTrigger: 'off'\n",
            "    autoDeployTrigger: 'off'\n    buildFilter: {}\n"))

    def test_disk_removed_or_changed_is_rejected(self):
        self.assert_rejected(self.valid.replace("      mountPath: /data", "      mountPath: /tmp"))
        self.assert_rejected(self.valid.replace("    disk:\n", ""))

    def test_secret_injection_is_rejected(self):
        self.assert_rejected(self.valid.replace(
            "        sync: false", "        value: exposed"))
        self.assert_rejected(self.valid.replace(
            "        sync: false", "        sync: false\n        value: exposed"))

    def test_inline_yaml_and_aliases_are_rejected(self):
        self.assert_rejected(self.valid.replace(
            "    autoDeployTrigger: 'off'", "    autoDeployTrigger: &mode off"))
        self.assert_rejected(self.valid.replace(
            "services:", "services: []"))

    def test_bom_tabs_and_multiple_roots_are_rejected(self):
        self.assert_rejected("\ufeff" + self.valid)
        self.assert_rejected(self.valid.replace("    runtime:", "\truntime:"))
        self.assert_rejected(self.valid + "\nservices:\n")

    def test_optimized_python_keeps_policy_enforced(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "render.yaml"
            path.write_text(self.valid.replace(
                "autoDeployTrigger: 'off'", "autoDeployTrigger: checksPass"),
                encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-O", str(MODULE_PATH), str(path)],
                capture_output=True, text=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("BOUNDARY: FAIL", result.stderr)


if __name__ == "__main__":
    unittest.main()
