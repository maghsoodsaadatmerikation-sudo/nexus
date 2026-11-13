#!/usr/bin/env python3
"""No-network adversarial tests for the six-PR Stage 21 gate."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('stage21', HERE / 'stage21-stack-preflight.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)

def healthy():
    sha = lambda i: f'{i:040x}'
    obj = {'repository': M.REPO, 'main_sha': sha(10), 'prs': []}
    previous = sha(10)
    for n, base, head in M.CHAIN:
        h = sha(n)
        names = sorted(M.REQUIRED | ({'research-chat'} if n >= 131 else set()))
        obj['prs'].append({
            'number': n, 'state': 'open', 'draft': False, 'mergeable': True,
            'base_ref': base, 'base_sha': previous, 'head_ref': head,
            'head_sha': h,
            'checks': [{'name': name, 'head_sha': h,
                        'status': 'completed', 'conclusion': 'success'}
                       for name in names]
        })
        previous = h
    return obj

class StackTest(unittest.TestCase):
    def blocked(self, mutator):
        data = healthy()
        mutator(data)
        with self.assertRaises(M.Blocked):
            M.validate(data)

    def test_healthy_stack_has_no_production_authority(self):
        report = M.validate(healthy())
        self.assertEqual(len(report['stack']), 6)
        self.assertIn('PASS', report['status'])
        self.assertEqual(report['original_railway_volume_recovery'], 'UNPROVEN')
        for key in ('production_merge_authorized', 'deployment_authorized', 'release_seal'):
            self.assertIs(report[key], False)

    def test_missing_pr(self): self.blocked(lambda d: d['prs'].pop(2))
    def test_bad_repository(self): self.blocked(lambda d: d.update(repository='other/repo'))
    def test_bad_main_sha(self): self.blocked(lambda d: d.update(main_sha='invalid'))
    def test_wrong_branch(self): self.blocked(lambda d: d['prs'][1].update(base_ref='main'))
    def test_drifted_parent(self): self.blocked(lambda d: d['prs'][3].update(base_sha='e'*40))
    def test_drifted_head(self): self.blocked(lambda d: d['prs'][3].update(head_sha='f'*40))
    def test_closed(self): self.blocked(lambda d: d['prs'][0].update(state='closed'))
    def test_draft(self): self.blocked(lambda d: d['prs'][5].update(draft=True))
    def test_merge_conflict(self): self.blocked(lambda d: d['prs'][1].update(mergeable=False))
    def test_unknown_merge_state(self): self.blocked(lambda d: d['prs'][1].update(mergeable=None))
    def test_pending(self): self.blocked(lambda d: d['prs'][2]['checks'][0].update(status='queued'))
    def test_failed(self): self.blocked(lambda d: d['prs'][2]['checks'][0].update(conclusion='failure'))
    def test_skipped(self): self.blocked(lambda d: d['prs'][2]['checks'][0].update(conclusion='skipped'))
    def test_wrong_sha_check(self): self.blocked(lambda d: d['prs'][2]['checks'][0].update(head_sha='e'*40))
    def test_missing_required(self): self.blocked(lambda d: d['prs'][5]['checks'].pop())
    def test_duplicate(self): self.blocked(lambda d: d['prs'][5]['checks'].append(copy.deepcopy(d['prs'][5]['checks'][0])))

    def test_cli_must_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / 'fixture.json'
            f.write_text(json.dumps(healthy()))
            command = [sys.executable, str(HERE / 'stage21-stack-preflight.py'), '--fixture', str(f)]
            ok = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(ok.returncode, 0)
            self.assertFalse(json.loads(ok.stdout)['deployment_authorized'])
            f.write_text('{}')
            bad = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(bad.returncode, 0)
            self.assertEqual(json.loads(bad.stdout)['status'], 'BLOCKED')

if __name__ == '__main__':
    unittest.main(verbosity=2)
