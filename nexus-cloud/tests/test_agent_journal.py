"""Durable one-time plan consumption, crash recovery evidence and private receipts."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from agent_workspace import Workspace, WorkspaceDenied
from agent_journal import ApprovalJournal
from engineering_agent import execute_plan, parse_plan


@pytest.fixture
def ws(tmp_path):
    root = tmp_path / 'private'
    root.mkdir(mode=0o700)
    return Workspace(root, 'sample')


def approved(ws, steps, *, nonce='1' * 32, version=3):
    plan = {'version': version, 'workspace': ws.name, 'steps': steps}
    if version >= 2:
        plan['expected_workspace_sha256'] = ws.manifest()['sha256']
    if version == 3:
        plan['execution_nonce'] = nonce
    return parse_plan(json.dumps(plan).encode())


def test_v3_one_time_read_only_consumes_approval(ws):
    ws.write('a', b'hello')
    plan, digest = approved(ws, [{'tool': 'read', 'path': 'a'}])
    before = ws.manifest()
    first = execute_plan(ws, plan, digest, approved_digest=digest)
    assert first.status == 'complete'
    assert first.workspace_sha256_before == first.workspace_sha256_after == before['sha256']
    assert ws.manifest() == before
    with pytest.raises(WorkspaceDenied, match='approval-already-consumed'):
        execute_plan(ws, plan, digest, approved_digest=digest)
    receipt = ApprovalJournal(ws).read(digest)
    assert receipt['state'] == 'finished' and receipt['result'] == 'complete'
    assert receipt['workspace_sha256_after'] == before['sha256']
    assert receipt['steps'] == [{'index': 0, 'status': 'completed', 'tool': 'read'}]
    assert 'hello' not in json.dumps(receipt)


def test_fresh_nonce_renews_explicitly_reviewed_same_read(ws):
    ws.write('a', b'hello')
    a, da = approved(ws, [{'tool': 'read', 'path': 'a'}], nonce='2' * 32)
    b, db = approved(ws, [{'tool': 'read', 'path': 'a'}], nonce='3' * 32)
    assert da != db
    assert execute_plan(ws, a, da, approved_digest=da).status == 'complete'
    assert execute_plan(ws, b, db, approved_digest=db).status == 'complete'


def test_failed_plan_is_single_use_and_retains_partial_file_and_receipt(ws):
    steps = [{'tool': 'write', 'path': 'created', 'text': 'private-token'},
             {'tool': 'verify_sha256', 'path': 'created', 'expected_sha256': '0' * 64}]
    p, d = approved(ws, steps)
    r = execute_plan(ws, p, d, approved_digest=d)
    assert r.status == 'step-denied'
    assert ws.read('created') == b'private-token'
    data = ApprovalJournal(ws).read(d)
    assert data['state'] == 'finished' and data['result'] == 'step-denied'
    assert data['steps'][1]['status'] == 'denied'
    assert 'private-token' not in json.dumps(data)
    with pytest.raises(WorkspaceDenied):
        execute_plan(ws, p, d, approved_digest=d)


def test_claim_survives_simulated_crash_before_first_action(ws):
    p, d = approved(ws, [{'tool': 'read', 'path': 'missing'}])
    journal = ApprovalJournal(ws)
    before = ws.manifest()['sha256']
    journal.claim(d, version=3, workspace_before=before, execution_nonce=p['execution_nonce'])
    # The simulated crash left no finalization, but it consumes approval.
    assert journal.read(d)['state'] == 'started'
    with pytest.raises(WorkspaceDenied, match='approval-already-consumed'):
        execute_plan(ws, p, d, approved_digest=d)
    assert ws.manifest()['sha256'] == before


def test_journal_not_in_workspace_fingerprint_and_private_permissions(ws):
    before = ws.manifest()
    p, d = approved(ws, [{'tool': 'search', 'query': 'absent', 'case_sensitive': False}])
    execute_plan(ws, p, d, approved_digest=d)
    assert ws.manifest() == before
    dpath = ws.root / '.nexus-agent-sample.journal'
    rec = dpath / (d + '.json')
    assert dpath.is_dir() and rec.is_file()
    assert dpath.stat().st_mode & 0o077 == 0
    assert rec.stat().st_mode & 0o077 == 0


def test_corrupt_and_symlinked_journal_deny(ws):
    p, d = approved(ws, [{'tool': 'read', 'path': 'missing'}])
    dpath = ws.root / '.nexus-agent-sample.journal'
    dpath.symlink_to('/tmp')
    with pytest.raises(OSError):
        execute_plan(ws, p, d, approved_digest=d)
    dpath.unlink()
    dpath.mkdir(mode=0o700)
    (dpath / (d + '.json')).write_text('not json')
    (dpath / (d + '.json')).chmod(0o600)
    with pytest.raises(WorkspaceDenied, match='approval-already-consumed'):
        execute_plan(ws, p, d, approved_digest=d)
    with pytest.raises(WorkspaceDenied, match='corrupt'):
        ApprovalJournal(ws).read(d)


def test_malformed_v3_nonce_and_missing_required_fields_fail_before_mutation(ws):
    base = {'version': 3, 'workspace': ws.name, 'expected_workspace_sha256': ws.manifest()['sha256'],
            'steps': [{'tool': 'write', 'path': 'never', 'text': 'bad'}]}
    for nonce in [None, 'a' * 31, 'x' * 32, 'A' * 32, True, 5, '0' * 65]:
        raw = dict(base)
        if nonce is not None:
            raw['execution_nonce'] = nonce
        with pytest.raises(WorkspaceDenied):
            parse_plan(json.dumps(raw).encode())
    assert not (ws.path / 'never').exists()


def test_workplace_change_does_not_consume_v3_approval(ws):
    p, d = approved(ws, [{'tool': 'write', 'path': 'never', 'text': 'no'}])
    ws.write('changed', b'x')
    with pytest.raises(WorkspaceDenied, match='workspace-state-changed'):
        execute_plan(ws, p, d, approved_digest=d)
    assert not (ws.root / '.nexus-agent-sample.journal').exists()


def test_legacy_version_one_approval_is_also_single_use(ws):
    ws.write('a', b'x')
    p, d = approved(ws, [{'tool': 'read', 'path': 'a'}], version=1)
    assert execute_plan(ws, p, d, approved_digest=d).status == 'complete'
    with pytest.raises(WorkspaceDenied, match='approval-already-consumed'):
        execute_plan(ws, p, d, approved_digest=d)


def test_cli_read_durable_receipt_without_re_execution(ws):
    cli = Path(__file__).resolve().parents[2] / 'scripts/nexus-engineering-plan.py'
    p, d = approved(ws, [{'tool': 'write', 'path': 'a', 'text': 'private content'}])
    plan_path = ws.root / 'plan.json'
    plan_path.write_text(json.dumps(p))
    base = [sys.executable, str(cli), '--root', str(ws.root), '--plan', str(plan_path)]
    apply = subprocess.run(base + ['--approve-digest', d], capture_output=True, text=True, timeout=8)
    assert apply.returncode == 0, apply.stderr
    r = subprocess.run(base + ['--receipt'], capture_output=True, text=True, timeout=8)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data['plan_sha256'] == d and data['state'] == 'finished'
    assert 'private content' not in r.stdout
    after = subprocess.run(base + ['--approve-digest', d], capture_output=True, text=True, timeout=8)
    assert after.returncode == 2  # It has already changed the workspace.


def test_claim_written_before_side_effect_and_unfinalized_on_exception(ws, monkeypatch):
    p, d = approved(ws, [{'tool': 'write', 'path': 'never', 'text': 'secret'}])
    import engineering_agent as module
    original_write = ws.write
    def interrupted(*args, **kwargs):
        assert ApprovalJournal(ws).read(d)['state'] == 'started'
        raise KeyboardInterrupt('simulated termination')
    monkeypatch.setattr(ws, 'write', interrupted)
    with pytest.raises(KeyboardInterrupt):
        module.execute_plan(ws, p, d, approved_digest=d)
    monkeypatch.setattr(ws, 'write', original_write)
    assert not (ws.path / 'never').exists()
    assert ApprovalJournal(ws).read(d)['state'] == 'started'
    with pytest.raises(WorkspaceDenied, match='approval-already-consumed'):
        execute_plan(ws, p, d, approved_digest=d)


def test_failed_journal_claim_denies_before_any_side_effect(ws, monkeypatch):
    p, d = approved(ws, [{'tool': 'write', 'path': 'never', 'text': 'unsafe'}])
    def fail_claim(*args, **kwargs):
        raise OSError('synthetic disk full')
    monkeypatch.setattr(ApprovalJournal, 'claim', fail_claim)
    with pytest.raises(OSError, match='disk full'):
        execute_plan(ws, p, d, approved_digest=d)
    assert not (ws.path / 'never').exists()


def test_failed_journal_completion_does_not_authorize_replay(ws, monkeypatch):
    p, d = approved(ws, [{'tool': 'write', 'path': 'created', 'text': 'hello'}])
    original = ApprovalJournal.finish
    def fail_finish(*args, **kwargs):
        raise OSError('synthetic fsync failure')
    monkeypatch.setattr(ApprovalJournal, 'finish', fail_finish)
    with pytest.raises(WorkspaceDenied, match='durable-receipt-failed'):
        execute_plan(ws, p, d, approved_digest=d)
    assert ws.read('created') == b'hello'
    assert ApprovalJournal(ws).read(d)['state'] == 'started'
    monkeypatch.setattr(ApprovalJournal, 'finish', original)
    with pytest.raises(WorkspaceDenied):
        execute_plan(ws, p, d, approved_digest=d)


def test_hardlinked_journal_record_rejected_for_read(ws):
    p, d = approved(ws, [{'tool': 'read', 'path': 'a'}])
    journal = ApprovalJournal(ws)
    journal.claim(d, version=3, workspace_before=ws.manifest()['sha256'], execution_nonce=p['execution_nonce'])
    record = ws.root / '.nexus-agent-sample.journal' / (d + '.json')
    os.link(record, ws.root / 'duplicate-record')
    with pytest.raises(WorkspaceDenied, match='unsafe'):
        journal.read(d)
