"""Phase 18: no fresh execution in a workspace with unfinished/unsafe claims."""
from __future__ import annotations
import hashlib
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from agent_chat_handoff import PROPOSAL_SCHEMA, prepare, write_export
from agent_journal import ApprovalJournal
from agent_operator_service import OperatorServer, client
from agent_workspace import Workspace, WorkspaceDenied
from engineering_agent import execute_plan, parse_plan


@pytest.fixture
def ws(tmp_path):
    root = tmp_path / 'private'; root.mkdir(mode=0o700)
    return Workspace(root, 'alpha')


def claim(ws, suffix='one', version=3):
    d = hashlib.sha256(suffix.encode()).hexdigest()
    with ws.operation_lock():
        ApprovalJournal(ws).claim(d, version=version,
                                  workspace_before=ws.manifest()['sha256'],
                                  execution_nonce='a'*32)
    return d


def execute_read(ws, nonce):
    raw = json.dumps({'version': 3, 'workspace': ws.name,
                      'expected_workspace_sha256': ws.manifest()['sha256'],
                      'execution_nonce': nonce, 'steps': [
                          {'tool': 'write', 'path': 'never.txt', 'text': 'secret'}]}).encode()
    plan, digest = parse_plan(raw)
    return execute_plan(ws, plan, digest, approved_digest=digest)


def test_stale_started_claim_quarantines_new_digest_even_when_plan_is_fresh(ws):
    assert ApprovalJournal(ws).audit()['status'] == 'clear'
    old = claim(ws)
    report = ApprovalJournal(ws).audit()
    assert report['status'] == 'blocked-unfinished'
    assert report['unfinished_digests'] == [old]
    assert report['finished_count'] == 0
    with pytest.raises(WorkspaceDenied, match='workspace-quarantined'):
        execute_read(ws, 'b'*32)
    assert not (ws.path/'never.txt').exists()
    with pytest.raises(WorkspaceDenied, match='approval-already-consumed'):
        with ws.operation_lock():
            ApprovalJournal(ws).claim(old, version=3, workspace_before=ws.manifest()['sha256'],
                                      execution_nonce='a'*32)


def test_finished_approval_restores_new_admission_without_deleting_evidence(ws):
    old = claim(ws)
    with ws.operation_lock():
        ApprovalJournal(ws).finish(old, status='cancelled',
                                    workspace_after=ws.manifest()['sha256'],
                                    completed_steps=0, step_summaries=[])
    audit = ApprovalJournal(ws).audit()
    assert audit == {'status': 'clear', 'finished_count': 1,
                     'unfinished_digests': [], 'authority': 'none'}
    assert execute_read(ws, 'c'*32).status == 'complete'
    assert (ws.path/'never.txt').read_text() == 'secret'
    assert ApprovalJournal(ws).read(old)['result'] == 'cancelled'


def test_unexpected_atomic_temporary_does_not_get_ignored(ws):
    first = claim(ws)
    journal = ApprovalJournal(ws)
    with ws.operation_lock():
        journal.finish(first, status='cancelled', workspace_after=ws.manifest()['sha256'],
                       completed_steps=0, step_summaries=[])
    leftover = ws.root/'.nexus-agent-alpha.journal'/('.nexus-journal-write-'+'1'*24)
    leftover.write_bytes(b'partial'); leftover.chmod(0o600)
    with pytest.raises(WorkspaceDenied, match='extra-entry'):
        journal.audit()
    with pytest.raises(WorkspaceDenied):
        execute_read(ws, 'd'*32)
    assert not (ws.path/'never.txt').exists()
    assert leftover.exists()


def test_symlinked_or_corrupt_other_receipt_blocks_admission(ws):
    old = claim(ws)
    entry = ws.root/'.nexus-agent-alpha.journal'/(old+'.json')
    entry.unlink()
    entry.symlink_to('/etc/passwd')
    with pytest.raises((WorkspaceDenied, OSError)): ApprovalJournal(ws).audit()
    with pytest.raises((WorkspaceDenied, OSError)): execute_read(ws, 'e'*32)
    entry.unlink()
    entry.write_text('{invalid-json'); entry.chmod(0o600)
    with pytest.raises(WorkspaceDenied, match='corrupt'):
        ApprovalJournal(ws).audit()
    assert not (ws.path/'never.txt').exists()


def test_truncated_finished_marker_without_final_receipt_blocks(ws):
    old = claim(ws)
    p = ws.root/'.nexus-agent-alpha.journal'/(old+'.json')
    receipt = json.loads(p.read_text())
    receipt['state'] = 'finished'
    p.write_text(json.dumps(receipt)); p.chmod(0o600)
    with pytest.raises(WorkspaceDenied, match='finished-record'):
        ApprovalJournal(ws).audit()
    with pytest.raises(WorkspaceDenied):execute_read(ws, 'f'*32)


@pytest.mark.skipif(os.getuid()==0,reason='operator Unix socket requires unprivileged owner')
def test_normal_operator_start_refused_after_unfinished_approval(ws, tmp_path):
    out = tmp_path/'out';out.mkdir(mode=0o700)
    ws.write('input.txt', b'safe')
    raw, review = prepare(ws, {'schema': PROPOSAL_SCHEMA, 'workspace': 'alpha',
                                'steps': [{'tool':'write', 'path':'never.txt','text':'private'}]})
    digest=review['plan_sha256']
    path=write_export(out,f'nexus-plan-{digest[:16]}.json',raw)
    old=claim(ws,'different-running-digest')
    service = OperatorServer(ws.root)
    listener = threading.Thread(target=service.serve_forever,
                                kwargs={'poll_interval':.01},daemon=True)
    listener.start()
    try:
        # Review does not execute; the attempt to queue MUST be quarantined.
        assert client(ws.root,workspace='alpha',digest=digest,action='review',plan_path=str(path))['status']=='review'
        blocked = client(ws.root,workspace='alpha',digest=digest,action='start',plan_path=str(path))
        assert blocked == {'status':'workspace-quarantined','authority':'none'}
        assert client(ws.root,workspace='alpha',digest=digest,action='status')['status']=='not-found'
        assert client(ws.root,workspace='alpha',digest=old,action='status')['journal_state']=='started'
        assert not (ws.path/'never.txt').exists()
        # A CLI audit never takes a capability token or modifies the journal.
        cli = Path(__file__).resolve().parents[2]/'scripts/nexus-operator-service.py'
        check = subprocess.run([sys.executable,str(cli),'audit-journal',
                                '--root',str(ws.root),'--workspace','alpha'],
                               capture_output=True,text=True,timeout=5)
        assert check.returncode==2,check.stderr
        report=json.loads(check.stdout)
        assert report['status']=='blocked-unfinished' and report['unfinished_digests']==[old]
        assert report['orphaned_processes_ruled_out'] is False
        assert report['jobs_restarted'] is False
        assert 'private' not in check.stdout
    finally:
        service.shutdown();listener.join(3);service.server_close()


def test_audit_is_read_only_and_does_not_create_nonexistent_workspace(ws):
    cli = Path(__file__).resolve().parents[2]/'scripts/nexus-operator-service.py'
    cmd=[sys.executable,str(cli),'audit-journal','--root',str(ws.root),'--workspace','missing']
    result=subprocess.run(cmd,capture_output=True,text=True,timeout=5)
    assert result.returncode==2
    assert not (ws.root/'missing').exists()
    ok=subprocess.run(cmd[:-1]+['alpha'],capture_output=True,text=True,timeout=5)
    assert ok.returncode==0 and json.loads(ok.stdout)['status']=='clear'


def test_other_workspace_not_implicitly_given_hostwide_attestation(ws):
    old=claim(ws,'orphan')
    second=Workspace(ws.root,'beta')
    assert execute_read(second,'1'*32).status=='complete'
    assert ApprovalJournal(ws).audit()['status']=='blocked-unfinished'
    assert ApprovalJournal(second).audit()['status']=='clear'
    assert old in ApprovalJournal(ws).audit()['unfinished_digests']

@pytest.mark.skipif(os.getuid()==0,reason='rootless operator requires unprivileged owner')
def test_rootless_operator_also_refuses_new_digest_after_started_plan(ws, tmp_path):
    from agent_rootless_job import prepare_job
    import shutil
    if not shutil.which('cc'):
        pytest.skip('static compiler required for real reviewed fixture')
    src=Path(__file__).resolve().parents[2]/'scripts/rootless-sandbox-probe.c'
    private=tmp_path/'bin'; private.mkdir(mode=0o700)
    binary=private/'reviewed'
    compile=subprocess.run(['cc','-static','-Os',str(src),'-o',str(binary)],
                           capture_output=True,text=True,timeout=35)
    assert compile.returncode==0,compile.stderr
    binary.chmod(0o500)
    digest_file=hashlib.sha256(binary.read_bytes()).hexdigest()
    ws.write('input.txt',b'sentinel')
    raw,meta=prepare_job(ws,binary,digest_file)
    out=tmp_path/'out';out.mkdir(mode=0o700)
    p=write_export(out,f"nexus-plan-{meta['plan_sha256'][:16]}.json",raw)
    previous=claim(ws,'different-approved-rootless-work')
    service=OperatorServer(ws.root,allow_rootless=True)
    listener=threading.Thread(target=service.serve_forever,
                              kwargs={'poll_interval':.01},daemon=True)
    listener.start()
    try:
        assert client(ws.root,workspace='alpha',digest=meta['plan_sha256'],
                      action='probe-review',plan_path=str(p))['status']=='review'
        result=client(ws.root,workspace='alpha',digest=meta['plan_sha256'],
                      action='probe-start',plan_path=str(p))
        assert result == {'status':'workspace-quarantined','authority':'none'}
        assert client(ws.root,workspace='alpha',digest=meta['plan_sha256'],
                      action='probe-status')['status']=='not-found'
        assert ApprovalJournal(ws).read(previous)['state']=='started'
    finally:
        service.shutdown();listener.join(3);service.server_close()


def test_invalid_entry_does_not_block_reading_existing_receipt(ws):
    old=claim(ws)
    journal=ApprovalJournal(ws)
    garbage=ws.root/'.nexus-agent-alpha.journal'/'BAD-NAME'
    garbage.write_text('x');garbage.chmod(0o600)
    assert journal.read(old)['state']=='started'
    with pytest.raises(WorkspaceDenied,match='extra-entry'):
        journal.audit()
    assert garbage.exists()
