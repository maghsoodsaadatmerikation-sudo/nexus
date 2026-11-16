import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from agent_workspace import Workspace, WorkspaceDenied
from agent_chat_handoff import (PROPOSAL_SCHEMA, parse_proposal, prepare,
                                chat_receipt, private_export_dir, write_export,
                                shareable_json, read_operator_file)
from engineering_agent import execute_plan, parse_plan
from agent_journal import ApprovalJournal

CLI = Path(__file__).resolve().parents[2] / 'scripts/nexus-chat-engineering.py'


@pytest.fixture
def setup(tmp_path):
    root = tmp_path / 'workspaces'
    root.mkdir(mode=0o700)
    out = tmp_path / 'outbox'
    out.mkdir(mode=0o700)
    return root, out, Workspace(root, 'project')


def proposal(steps=None):
    return {'schema': PROPOSAL_SCHEMA, 'workspace': 'project',
            'steps': steps or [{'tool': 'write', 'path': 'notes.txt', 'text': 'private-secret-canary'}]}


def raw(value):
    return json.dumps(value).encode()


def test_prepare_does_not_execute_and_makes_real_v3_plan(setup):
    root, out, workspace = setup
    p = parse_proposal(raw(proposal()))
    before = workspace.manifest()['sha256']
    plan_bytes, review = prepare(workspace, p)
    plan, digest = parse_plan(plan_bytes)
    assert plan['version'] == 3 and plan['expected_workspace_sha256'] == before
    assert plan['execution_nonce'] != '0'*32 and len(plan['execution_nonce']) == 32
    assert digest == review['plan_sha256']
    assert review['status'] == 'not-executed' and review['review_required']
    assert not (workspace.path / 'notes.txt').exists()
    assert workspace.manifest()['sha256'] == before
    assert b'private-secret-canary' not in shareable_json(review)


def test_fresh_review_nonce_changes_exact_approval_even_with_same_files(setup):
    _, _, ws = setup
    p = proposal([{'tool':'read','path':'exists.txt'}])
    _, r1 = prepare(ws,p)
    _, r2 = prepare(ws,p)
    assert r1['plan_sha256'] != r2['plan_sha256']


@pytest.mark.parametrize('data', [
    b'{"schema":"nexus.engineering.proposal.v1","workspace":"project","workspace":"evil","steps":[]}',
    b'{"schema":"nexus.engineering.proposal.v1","workspace":"project","steps":[{"tool":"run","image":"unsigned:latest","argv":["sh"],"timeout_seconds":10}]}',
    b'{"schema":"nexus.engineering.proposal.v1","workspace":"project","steps":[{"tool":"write","path":"../outside","text":"danger"}]}',
    b'{"schema":"nexus.engineering.proposal.v1","workspace":"project","steps":[{"tool":"read","path":"ok"}],"approve_digest":"abc"}',
    b'{"schema":"nexus.engineering.proposal.v1","workspace":"project","steps":[{"tool":"read","path":"ok","tool":"run"}]}',
    b'{"schema":"nexus.engineering.proposal.v1","workspace":"project","steps":[{"tool":"read","path":"ok"}],"version":3}',
    b'{"schema":"nexus.engineering.proposal.v1","workspace":"project","steps":[{"tool":"run","image":"x@sha256:' + b'a'*64 + b'","argv":["sh"],"timeout_seconds":true}]}',
    b'{"schema":"nexus.engineering.proposal.v1","workspace":"project","steps":[{"tool":"read","path":"ok"}],"nonce":NaN}',
    b'{"schema":"nexus.engineering.proposal.v1","workspace":"project","steps":[{"tool":"read","path":"ok"}]}TRAIL',
    b'\xff',
    b' ',
    b'x'*32769,
])
def test_hostile_proposal_rejected_before_approval(data):
    with pytest.raises(WorkspaceDenied):
        parse_proposal(data)


def test_workspace_mismatch_never_executed(setup):
    _, _, workspace = setup
    with pytest.raises(WorkspaceDenied, match='mismatch'):
        prepare(workspace, {**proposal(), 'workspace':'other'})


def test_shareable_receipt_from_real_journal_has_no_sensitive_text(setup):
    _, _, ws = setup
    plan_bytes, review = prepare(ws,proposal())
    plan, digest = parse_plan(plan_bytes)
    result = execute_plan(ws,plan,digest,approved_digest=digest)
    assert result.status == 'complete'
    with ws.operation_lock():
        record = ApprovalJournal(ws).read(digest)
    chat = chat_receipt(record)
    content = shareable_json(chat)
    assert chat['execution_status'] == 'complete'
    assert chat['journal_state'] == 'finished'
    assert chat['workspace_sha256_before'] != chat['workspace_sha256_after']
    assert 'notes.txt' not in content.decode()
    assert 'private-secret-canary' not in content.decode()
    assert 'read-only' not in content.decode()
    assert b'"authority": "none"' in content
    with pytest.raises(WorkspaceDenied, match='reapproval-required|consumed'):
        execute_plan(ws,plan,digest,approved_digest=digest)


def test_crash_started_record_does_not_forge_success(setup):
    _, _, ws = setup
    plan_bytes, review = prepare(ws,proposal([{'tool':'read','path':'missing'}]))
    plan, digest = parse_plan(plan_bytes)
    with ws.operation_lock():
        ApprovalJournal(ws).claim(digest,version=3,workspace_before=ws.manifest()['sha256'],execution_nonce=plan['execution_nonce'])
        record=ApprovalJournal(ws).read(digest)
    message = chat_receipt(record)
    assert message['execution_status']=='interrupted-or-in-progress'
    assert message['workspace_sha256_after'] is None
    assert message['steps'] == []
    assert message['verification'] == 'not-independent-attestation'


@pytest.mark.parametrize('record',[{}, {'state':'finished','plan_sha256':'x','workspace_sha256_before':'x'}, {'state':'finished','plan_sha256':'a'*64,'workspace_sha256_before':'a'*64,'result':'complete','steps':[{'tool':'unknown','index':0,'status':'completed'}]}])
def test_forged_journal_is_rejected(record):
    with pytest.raises(WorkspaceDenied):
        chat_receipt(record)


def test_private_output_cannot_be_inside_workspace_or_public_or_symlink(setup, tmp_path):
    root, out, ws = setup
    assert private_export_dir(out,ws)==out
    with pytest.raises(WorkspaceDenied): private_export_dir(ws.path,ws)
    out.chmod(0o755)
    with pytest.raises(WorkspaceDenied): private_export_dir(out,ws)
    out.chmod(0o700)
    alias=tmp_path / 'alias'
    alias.symlink_to(out)
    with pytest.raises(WorkspaceDenied): private_export_dir(alias,ws)


def test_exports_private_exclusive_and_no_symlink_overwrite(setup):
    _, out, ws=setup
    d='a'*16
    name=f'nexus-review-{d}.txt'
    p=write_export(out,name,b'private-message')
    assert stat.S_IMODE(p.stat().st_mode)==0o600
    with pytest.raises(WorkspaceDenied,match='exists'):
        write_export(out,name,b'changed')
    assert p.read_bytes()==b'private-message'
    name2=f'nexus-result-{d}.txt'
    (out / name2).symlink_to(p)
    with pytest.raises((WorkspaceDenied,OSError)):
        write_export(out,name2,b'overwrite-attempt')
    assert p.read_bytes()==b'private-message'


def test_cli_prepare_execute_receipt_end_to_end(setup, tmp_path):
    root, out, ws=setup
    draft = tmp_path/'proposal.json'
    draft.write_bytes(raw(proposal()))
    def cli(*args):
        return subprocess.run([sys.executable,str(CLI),*args],capture_output=True,text=True,timeout=10)
    common=('--root',str(root),'--workspace','project')
    a=cli('prepare',*common,'--proposal',str(draft),'--out',str(out))
    assert a.returncode==0,a.stderr
    packet=json.loads(a.stdout)
    assert packet['status']=='prepared-not-executed'
    assert not (ws.path/'notes.txt').exists()
    assert Path(packet['private_plan']).exists() and Path(packet['chat_review']).exists()
    digest=packet['plan_sha256']
    bad=cli('execute',*common,'--plan',packet['private_plan'],'--out',str(out),'--approve-digest','f'*64)
    assert bad.returncode==2 and not (ws.path/'notes.txt').exists()
    ok=cli('execute',*common,'--plan',packet['private_plan'],'--out',str(out),'--approve-digest',digest)
    assert ok.returncode==0,ok.stderr
    result=json.loads(ok.stdout)
    assert result['status']=='complete'
    assert 'private-secret-canary' not in Path(result['chat_result']).read_text()
    assert (ws.path/'notes.txt').read_text()=='private-secret-canary'
    replay=cli('execute',*common,'--plan',packet['private_plan'],'--out',str(out),'--approve-digest',digest)
    assert replay.returncode==2 and ('consumed' in replay.stderr or 'reapproval-required' in replay.stderr)
    receipt=cli('receipt',*common,'--plan',packet['private_plan'])
    assert receipt.returncode==0
    assert json.loads(receipt.stdout)['execution_status']=='complete'


def test_cli_rejects_implied_or_missing_authority(setup, tmp_path):
    root,out,_=setup
    p=tmp_path/'p.json';p.write_bytes(raw(proposal()))
    proc=subprocess.run([sys.executable,str(CLI),'prepare','--root',str(root),'--workspace','project','--proposal',str(p),'--out',str(out),'--approve-digest','a'*64],capture_output=True,text=True)
    assert proc.returncode==2
    assert not list(out.iterdir())


def test_bounded_input_refuses_symlinks_and_oversized_file(tmp_path):
    oversized = tmp_path / 'oversized.json'
    with open(oversized, 'wb') as stream:
        stream.truncate(100 * 1024 * 1024)
    with pytest.raises(WorkspaceDenied):
        read_operator_file(oversized)
    real = tmp_path / 'real.json'
    real.write_bytes(b'{"test":true}')
    link = tmp_path / 'link.json'
    link.symlink_to(real)
    with pytest.raises(OSError):
        read_operator_file(link)
    assert read_operator_file(real) == b'{"test":true}'
