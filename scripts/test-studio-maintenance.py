#!/usr/bin/env python3
"""Regression tests for the Studio maintenance release-safety boundary."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "studio_maintenance", Path(__file__).with_name("studio-maintenance.py")
)
maintenance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(maintenance)


class ReproducibilityTests(unittest.TestCase):
    def invoke(self, args, builds):
        output = io.StringIO()
        with patch("sys.argv", ["studio-maintenance.py", *args]), \
             patch.object(maintenance, "inspect", side_effect=builds) as inspect, \
             patch.object(maintenance, "git", return_value=b"base\n") as git, \
             patch.object(maintenance, "require_base"), \
             contextlib.redirect_stdout(output):
            code = maintenance.main()
        return code, json.loads(output.getvalue()), inspect, git

    def test_default_audit_builds_once(self):
        code, report, inspect, git = self.invoke([], [([], b"")])
        self.assertEqual(code, 0)
        self.assertEqual(report["reproducibility"], "not_checked")
        self.assertEqual(report["patch_sha256"], hashlib.sha256(b"").hexdigest())
        inspect.assert_called_once_with("base")
        self.assertFalse(any("apply" in call.args for call in git.call_args_list))

    def test_matching_drift_audit_is_read_only(self):
        result = (["web/studio.html"], b"patch")
        code, report, inspect, git = self.invoke(["--reproducible"], [result, result])
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "drift")
        self.assertEqual(report["reproducibility"], "matched")
        self.assertEqual(report["patch_sha256"], hashlib.sha256(b"patch").hexdigest())
        self.assertEqual(inspect.call_count, 2)
        self.assertFalse(any("apply" in call.args for call in git.call_args_list))

    def test_repair_mismatch_never_applies(self):
        code, report, inspect, git = self.invoke(
            ["--repair"], [(["web/studio.html"], b"a"), (["web/studio.html"], b"b")]
        )
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(inspect.call_count, 2)
        self.assertFalse(any("apply" in call.args for call in git.call_args_list))

    def test_repair_matching_patch_checks_before_apply(self):
        result = (["web/studio.html"], b"patch")
        code, report, inspect, git = self.invoke(["--repair"], [result, result])
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "repaired")
        self.assertEqual(inspect.call_count, 2)
        calls = [call for call in git.call_args_list if "apply" in call.args]
        self.assertEqual([call.args[1:] for call in calls],
                         [("apply", "--check", "-"), ("apply", "-")])
        self.assertTrue(all(call.kwargs["patch"] == b"patch" for call in calls))

    def test_second_build_failure_blocks_repair(self):
        code, report, inspect, git = self.invoke(
            ["--repair"], [(["web/studio.html"], b"a"), RuntimeError("builder failed")]
        )
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(any("apply" in call.args for call in git.call_args_list))


if __name__ == "__main__":
    unittest.main()
