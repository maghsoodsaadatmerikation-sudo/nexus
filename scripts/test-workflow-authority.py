#!/usr/bin/env python3
"""Adversarial tests for read-only PR and privileged workflow boundaries."""

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

MODULE_PATH = Path(__file__).with_name('verify-workflow-authority.py')


def load_verifier():
    spec = importlib.util.spec_from_file_location('nexus_workflow_authority', MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PR = '''name: Test
on:
  pull_request:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - run: echo check
'''
PRIV = '''name: Attestation
on:
  push:
    branches: [main]
permissions:
  contents: read
  id-token: write
  attestations: write
jobs:
  attest:
    runs-on: ubuntu-latest
'''


class WorkflowAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.verifier = load_verifier()
        root = Path(self.tmp.name)
        self.workflow_root = root / '.github' / 'workflows'
        self.workflow_root.mkdir(parents=True)
        for name in self.verifier.PR_WORKFLOWS:
            (self.workflow_root / name).write_text(PR, encoding='utf-8')
        for name in self.verifier.PRIVILEGED:
            (self.workflow_root / name).write_text(PRIV, encoding='utf-8')
        self.verifier.WORKFLOWS = self.workflow_root

    def replace(self, name, source):
        (self.workflow_root / name).write_text(source, encoding='utf-8')

    def test_read_only_policy_accepts_valid_workflows(self):
        self.verifier.check()

    def test_pr_write_scopes_are_rejected(self):
        for scope in ('contents', 'actions', 'packages', 'deployments', 'pages', 'issues',
                      'pull-requests', 'security-events', 'id-token', 'attestations'):
            with self.subTest(scope=scope):
                self.replace('extra.yaml', PR.replace('  contents: read',
                    '  contents: read\n  ' + scope + ': write'))
                with self.assertRaises(ValueError):
                    self.verifier.check()
                (self.workflow_root / 'extra.yaml').unlink()

    def test_pr_job_level_escalation_rejected(self):
        self.replace('extra.yml', PR + '    permissions:\n      actions: write\n')
        with self.assertRaises(ValueError):
            self.verifier.check()

    def test_write_all_or_inline_permission_syntax_rejected(self):
        for altered in ('permissions: write-all',
                        'permissions: {contents: read, id-token: write}',
                        'permissions: read-all'):
            with self.subTest(altered=altered):
                self.replace('extra.yml', PR.replace('permissions:\n  contents: read', altered))
                with self.assertRaises(ValueError):
                    self.verifier.check()
                (self.workflow_root / 'extra.yml').unlink()

    def test_missing_explicit_root_permissions_rejected(self):
        self.replace('extra.yml', PR.replace('permissions:\n  contents: read\n', ''))
        with self.assertRaises(ValueError):
            self.verifier.check()

    def test_pr_target_is_forbidden_even_when_read_only(self):
        self.replace('extra.yml', PR.replace('pull_request:', 'pull_request_target:'))
        with self.assertRaises(ValueError):
            self.verifier.check()

    def test_unrecognized_event_indentation_and_quoted_triggers_fail(self):
        for altered in ('    pull_request_target:', '  "pull_request_target":'):
            with self.subTest(altered=altered):
                self.replace('extra.yml', PR.replace('  pull_request:', altered))
                with self.assertRaises(ValueError):
                    self.verifier.check()
                (self.workflow_root / 'extra.yml').unlink()

    def test_privileged_pr_trigger_is_forbidden(self):
        name = self.verifier.PRIVILEGED[0]
        self.replace(name, PRIV.replace('  push:', '  pull_request:\n  push:'))
        with self.assertRaises(ValueError):
            self.verifier.check()

    def test_unknown_workflow_permission_syntax_fails_closed(self):
        self.replace('extra.yml', PR.replace('  contents: read', '  contents: unspecified'))
        with self.assertRaises(ValueError):
            self.verifier.check()

    def test_optimized_python_cannot_disable_boundary(self):
        self.replace('extra.yml', PR.replace('  contents: read', '  contents: write'))
        code = ("import importlib.util; p='" + str(MODULE_PATH) + "'; "
                "s=importlib.util.spec_from_file_location('a',p); "
                "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                "m.WORKFLOWS='" + str(self.workflow_root) + "'; "
                "m.check()")
        result = subprocess.run([sys.executable, '-O', '-c', code],
                                text=True, capture_output=True, check=False)
        self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
