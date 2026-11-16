"""Phase 19: host-root admission fence, read-only inventories and concurrency."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import threading

import pytest

from agent_host_census import admission_lock, journal_census, docker_inventory, HOST_LOCK_NAME
from agent_journal import ApprovalJournal
from agent_workspace import Workspace, WorkspaceDenied
from engineering_agent import parse_plan, execute_plan


def init(tmp_path, name):
    root = tmp_path / 'private'
    root.mkdir(mode=0o700, exist_ok=True)
    return Workspace(root, name)


def claim(ws, label):
    sha = hashlib.sha256(label.encode()).hexdigest()
    with ws.operation_lock():
        ApprovalJournal(ws).claim(sha, version=3,workspace_before=ws.manifest()['sha256'],execution_nonce='a'*32)
    return sha


def finalize(ws, sha):
    with ws.operation_lock():
        ApprovalJournal(ws).finish(sha,status='cancelled',workspace_after=ws.manifest()['sha256'],completed_steps=0,step_summaries=[])


def test_quarantine_across_two_workspaces_and_receipts_never_erased(tmp_path):
    a=init(tmp_path,'alpha');b=Workspace(a.root,'beta')
    sha=claim(a,'running-plan')
    report=journal_census(a.root)
    assert report['status']=='blocked-unfinished'
    assert report['unfinished']==[{'workspace':'alpha','plan_sha256':sha}]
    assert report['orphaned_processes_ruled_out'] is False
    with pytest.raises(WorkspaceDenied,match='host-quarantined'):
        claim(b,'independent-plan')
    assert not (b.root/'.nexus-agent-beta.journal').exists()
    assert ApprovalJournal(a).read(sha)['state']=='started'
    with pytest.raises(WorkspaceDenied,match='approval-already-consumed'):
        claim(a,'running-plan')
    finalize(a,sha)
    assert journal_census(a.root)['status']=='clear'
    second=claim(b,'independent-plan')
    assert ApprovalJournal(b).read(second)['state']=='started'
    assert ApprovalJournal(a).read(sha)['result']=='cancelled'


def test_root_guard_serializes_simultaneous_claims(tmp_path):
    a=init(tmp_path,'alpha');b=Workspace(a.root,'beta')
    barrier=threading.Barrier(2)
    results=[]
    def worker(ws, tag):
        barrier.wait()
        try:
            results.append(('accepted',claim(ws,tag)))
        except WorkspaceDenied as exc:
            results.append(('denied',str(exc)))
    threads=[threading.Thread(target=worker,args=(a,'first')),threading.Thread(target=worker,args=(b,'second'))]
    for t in threads:t.start()
    for t in threads:t.join(8);assert not t.is_alive()
    assert sorted(x[0] for x in results)==['accepted','denied'],results
    assert journal_census(a.root)['status']=='blocked-unfinished'
    assert (a.root/HOST_LOCK_NAME).stat().st_mode & 0o077==0


def test_unknown_and_corrupt_other_workspace_journal_fail_closed(tmp_path):
    a=init(tmp_path,'alpha');b=Workspace(a.root,'beta')
    sha=claim(a,'finished');finalize(a,sha)
    malicious=a.root/'.nexus-agent-invalid name.journal'
    malicious.mkdir(mode=0o700)
    with pytest.raises(WorkspaceDenied,match='unknown-journal'):
        journal_census(a.root)
    with pytest.raises(WorkspaceDenied):claim(b,'blocked-1')
    malicious.rmdir()
    other=a.root/'.nexus-agent-alpha.journal'
    moved=a.root/'.nexus-agent-alpha.journal-original'
    other.rename(moved)
    other.symlink_to(moved,target_is_directory=True)
    with pytest.raises(WorkspaceDenied,match='journal-unsafe'):
        journal_census(a.root)
    with pytest.raises(WorkspaceDenied):claim(b,'blocked-2')


def test_dangling_journal_and_workspace_directory_fail_closed(tmp_path):
    a=init(tmp_path,'alpha');b=Workspace(a.root,'beta')
    claim(a,'first')
    (a.root/'alpha').rename(a.root/'missing-workspace')
    with pytest.raises((OSError,WorkspaceDenied)):
        journal_census(a.root)
    with pytest.raises((OSError,WorkspaceDenied)):
        claim(b,'second')


def test_nonprivate_host_lock_and_symlink_ancestor_refused(tmp_path):
    a=init(tmp_path,'alpha')
    lock=a.root/HOST_LOCK_NAME
    lock.write_bytes(b'')
    lock.chmod(0o644)
    with pytest.raises(WorkspaceDenied,match='lock-unsafe'):
        with admission_lock(a.root):pass
    lock.chmod(0o600)
    with admission_lock(a.root):pass
    alias=tmp_path/'link';alias.symlink_to(a.root,target_is_directory=True)
    with pytest.raises((OSError,WorkspaceDenied)):
        journal_census(alias)


def test_docker_inventory_is_read_only_and_never_attests_absence(tmp_path,monkeypatch):
    binary=tmp_path/'mockdocker'
    recorded=tmp_path/'argv.json'
    contents='''#!/usr/bin/env python3
import json,sys
from pathlib import Path
Path(%r).write_text(json.dumps(sys.argv[1:]))
print(%r)
'''%(str(recorded),'a'*64)
    binary.write_text(contents);binary.chmod(0o700)
    monkeypatch.setenv('PATH',str(tmp_path)+':/usr/bin:/bin')
    data=docker_inventory(executable='mockdocker')
    assert data['status']=='labelled-containers-observed'
    assert data['container_ids']==['a'*64]
    assert data['orphaned_processes_ruled_out'] is False
    args=json.loads(recorded.read_text())
    assert args==['ps','--all','--no-trunc','--filter','label=nexus.operator.managed=1','--format','{{.ID}}']
    binary.write_text(contents.replace("print(%r)"%('a'*64),"sys.stdout.write('')"))
    report=docker_inventory(executable='mockdocker')
    assert report['status']=='no-labelled-containers-observed'
    assert report['orphaned_processes_ruled_out'] is False
    assert docker_inventory(executable='missing-client-for-ci')['status']=='unverifiable'


def test_docker_inventory_corrupt_output_is_unverifiable(tmp_path,monkeypatch):
    binary=tmp_path/'mockdocker';binary.write_text('#!/bin/sh\necho NOT-HEX\n');binary.chmod(0o700)
    monkeypatch.setenv('PATH',str(tmp_path)+':/usr/bin:/bin')
    assert docker_inventory(executable='mockdocker')['status']=='unverifiable'
    binary.write_text('#!/bin/sh\nexit 1\n')
    assert docker_inventory(executable='mockdocker')['status']=='unverifiable'

@pytest.mark.skipif(os.getuid()==0,reason='operator socket requires nonroot')
def test_operator_admission_refuses_other_workspace_started_before_queue(tmp_path):
    from agent_chat_handoff import PROPOSAL_SCHEMA, prepare, write_export
    from agent_operator_service import OperatorServer, client
    a=init(tmp_path,'alpha');b=Workspace(a.root,'beta')
    old=claim(a,'orphan-from-other-workspace')
    b.write('input.txt',b'safe')
    raw, review=prepare(b,{'schema':PROPOSAL_SCHEMA,'workspace':'beta',
                          'steps':[{'tool':'write','path':'never.txt','text':'NO'}]})
    out=tmp_path/'out';out.mkdir(mode=0o700)
    path=write_export(out,f"nexus-plan-{review['plan_sha256'][:16]}.json",raw)
    with OperatorServer(a.root) as service:
        decision=service.dispatch({'action':'start','workspace':'beta',
                                   'digest':review['plan_sha256'],
                                   'plan_path':str(path),'token':service._token},os.getuid())
        assert decision=={'status':'host-quarantined','authority':'none'}
    assert not (b.path/'never.txt').exists()
    assert ApprovalJournal(a).read(old)['state']=='started'


def test_read_only_host_audit_cli_is_unprivileged_and_cannot_clear(tmp_path):
    a=init(tmp_path,'alpha');b=Workspace(a.root,'beta')
    old=claim(a,'unresolved-host-plan')
    cli=Path(__file__).resolve().parents[2]/'scripts/nexus-operator-service.py'
    cmd=[sys.executable,str(cli),'audit-host','--root',str(a.root)]
    status=subprocess.run(cmd,capture_output=True,text=True,timeout=5)
    assert status.returncode==2
    result=json.loads(status.stdout)
    assert result['status']=='blocked-unfinished'
    assert result['unfinished']==[{'workspace':'alpha','plan_sha256':old}]
    assert result['jobs_restarted'] is False
    assert result['orphaned_processes_ruled_out'] is False
    assert not (b.root/'.nexus-agent-beta.journal').exists()
    assert ApprovalJournal(a).read(old)['state']=='started'
    finalize(a,old)
    clear=subprocess.run(cmd,capture_output=True,text=True,timeout=5)
    assert clear.returncode==0
    report=json.loads(clear.stdout)
    assert report['status']=='clear' and report['orphaned_processes_ruled_out'] is False
    invalid=subprocess.run([*cmd,'--workspace','alpha'],capture_output=True,text=True,timeout=5)
    assert invalid.returncode==2 and 'denied' in invalid.stderr
