#!/usr/bin/env python3
"""Hostile fixtures for NEXUS CI authority boundary (no network/secrets)."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

THIS = Path(__file__).with_name('verify-workflow-authority.py')
spec = importlib.util.spec_from_file_location('workflow_authority', THIS)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def workflow(*, event='pull_request', global_permissions='  contents: read',
             job_permissions='', prefix='', trailing=''):
    return (f'{prefix}name: synthetic\n'
            f'on:\n  {event}:\n'
            f'permissions:\n{global_permissions}\n'
            f'jobs:\n  test:\n    runs-on: ubuntu-24.04\n'
            f'{job_permissions}    steps:\n'
            f'      - run: echo safe\n{trailing}')


class TestWorkflowAuthority(unittest.TestCase):
    def reject(self, source):
        with self.assertRaises(mod.BoundaryError):
            mod.inspect_workflow(source, 'synthetic.yml')

    def test_valid_pull_request(self):
        triggers, perms = mod.inspect_workflow(workflow(), 'synthetic.yml')
        self.assertEqual(triggers, {'pull_request'})
        self.assertEqual(perms['contents'], 'read')

    def test_valid_read_only_job_override(self):
        src = workflow(job_permissions='    permissions:\n      contents: read\n')
        self.assertEqual(mod.inspect_workflow(src, 'synthetic.yml')[0], {'pull_request'})

    def test_push_publish_not_misidentified_as_pr(self):
        src = workflow(event='push', global_permissions='  contents: write')
        self.assertEqual(mod.inspect_workflow(src, 'synthetic.yml')[0], {'push'})

    def test_pull_request_target_denied_even_read_only(self):
        self.reject(workflow(event='pull_request_target'))

    def test_merge_group_denies_write(self):
        self.reject(workflow(event='merge_group', global_permissions='  contents: write'))

    def test_issue_comment_denies_write(self):
        self.reject(workflow(event='issue_comment', global_permissions='  contents: write'))

    def test_global_contents_write_denied(self):
        self.reject(workflow(global_permissions='  contents: write'))

    def test_global_id_token_write_denied(self):
        self.reject(workflow(global_permissions='  contents: read\n  id-token: write'))

    def test_job_level_write_denied(self):
        self.reject(workflow(job_permissions='    permissions:\n      statuses: write\n'))

    def test_job_inline_permission_denied(self):
        self.reject(workflow(job_permissions='    permissions: {contents: write}\n'))

    def test_global_inline_permission_denied(self):
        self.reject(workflow().replace('permissions:\n  contents: read',
                                       'permissions: {contents: write}'))

    def test_global_write_all_denied(self):
        self.reject(workflow().replace('permissions:\n  contents: read',
                                       'permissions: write-all'))

    def test_missing_permissions_denied(self):
        self.reject(workflow().replace('permissions:\n  contents: read\n', ''))

    def test_inline_events_denied(self):
        self.reject(workflow().replace('on:\n  pull_request:',
                                       'on: [pull_request]'))

    def test_duplicate_top_level_on_denied(self):
        self.reject(workflow(prefix='on:\n  push:\n'))

    def test_duplicate_permission_keys_denied(self):
        self.reject(workflow(global_permissions='  contents: read\n  contents: write'))

    def test_duplicate_job_permissions_denied(self):
        self.reject(workflow(job_permissions=('    permissions:\n      contents: read\n'
                                              '    permissions:\n      contents: write\n')))

    def test_alias_and_expression_permissions_denied(self):
        self.reject(workflow(global_permissions='  contents: *trusted'))
        self.reject(workflow(global_permissions='  contents: ' + '$' + '{{ github.event_name }}'))

    def test_comment_and_run_script_not_an_event_or_permission(self):
        src = workflow(trailing='') + '      - run: |\n          echo "pull_request_target: contents: write"\n'
        self.assertEqual(mod.inspect_workflow(src, 'synthetic.yml')[0], {'pull_request'})

    def test_no_assert_based_security_gate(self):
        # python -O drops assert statements; security checks must still run.
        self.assertNotIn('assert ', THIS.read_text(encoding='utf-8'))

    def test_directory_contract(self):
        with tempfile.TemporaryDirectory() as d:
            wd = Path(d)
            for filename in mod.PRIVILEGED:
                (wd / filename).write_text(
                    'name: gate\non:\n  push:\n    branches: [main]\n'
                    '  workflow_dispatch:\npermissions:\n  contents: read\n'
                    '  id-token: write\n  attestations: write\n'
                    'jobs:\n  attest:\n    runs-on: ubuntu-24.04\n', encoding='utf-8')
            for filename in mod.PR_WORKFLOWS:
                (wd / filename).write_text(workflow(), encoding='utf-8')
            mod.check(wd)
            (wd / 'new-untrusted.yml').write_text(
                workflow(event='pull_request', global_permissions='  contents: write'), encoding='utf-8')
            with self.assertRaises(mod.BoundaryError):
                mod.check(wd)


if __name__ == '__main__':
    unittest.main(verbosity=2)
