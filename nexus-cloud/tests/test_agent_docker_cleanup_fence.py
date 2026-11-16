"""Fail-closed Docker cleanup fence: no terminal success from an uncertain daemon."""
import hashlib
import json
import os
from pathlib import Path
from unittest import mock
import pytest

from agent_host_census import (DOCKER_UNVERIFIED_PREFIX, journal_census,
                               record_unverified_docker_cleanup)
from agent_journal import ApprovalJournal
from agent_workspace import (CleanupUnverifiable, Workspace, WorkspaceDenied,
                             run_container)
from engineering_agent import execute_plan, parse_plan


def space(tmp_path):
    root=tmp_path/'private';root.mkdir(mode=0o700)
    return Workspace(root,'alpha')


def claim(ws,label):
    digest=hashlib.sha256(label.encode()).hexdigest()
    with ws.operation_lock():
        ApprovalJournal(ws).claim(
            digest,version=3,workspace_before=ws.manifest()['sha256'],
            execution_nonce='a'*32)
    return digest


class Pipe:
    def __init__(self):
        self.read,self.write=os.pipe();os.close(self.write)
    def fileno(self):return self.read


class FailedCli:
    returncode=1
    def __init__(self,*args,**kwargs):
        self.stdout=Pipe();self.stderr=Pipe()
    def poll(self):return 1
    def wait(self,timeout=None):return 1


def test_persisted_uncertainty_blocks_all_workspaces(tmp_path):
    ws=space(tmp_path)
    other=Workspace(ws.root,'beta')
    record_unverified_docker_cleanup(ws.root)
    report=journal_census(ws.root)
    assert report['status']=='blocked-unverified-container'
    assert report['docker_cleanup_unverified_count']==1
    assert report['orphaned_processes_ruled_out'] is False
    with pytest.raises(WorkspaceDenied,match='host-quarantined'):
        claim(other,'new-approval')
    assert not (other.root/'.nexus-agent-beta.journal').exists()


def test_malformed_evidence_and_renamed_journal_cannot_disappear(tmp_path):
    ws=space(tmp_path)
    bad=ws.root/(DOCKER_UNVERIFIED_PREFIX+'a'*24+'.marker')
    bad.symlink_to('/etc/passwd')
    with pytest.raises((OSError,WorkspaceDenied)):
        journal_census(ws.root)
    bad.unlink()
    bad.write_bytes(b'garbled');bad.chmod(0o600)
    with pytest.raises(WorkspaceDenied,match='unsafe-docker-evidence'):
        journal_census(ws.root)
    bad.unlink()
    old=claim(ws,'old')
    with ws.operation_lock():
        ApprovalJournal(ws).finish(old,status='cancelled',
            workspace_after=ws.manifest()['sha256'],
            completed_steps=0,step_summaries=[])
    (ws.root/'.nexus-agent-alpha.journal').rename(
        ws.root/'.nexus-agent-alpha.journal-stale')
    with pytest.raises(WorkspaceDenied,match='unknown-journal'):
        journal_census(ws.root)


def test_failed_docker_cli_without_cid_persists_host_fence(tmp_path,monkeypatch):
    ws=space(tmp_path)
    monkeypatch.setattr('agent_workspace.shutil.which',lambda _: '/usr/bin/docker')
    monkeypatch.setattr('agent_workspace.subprocess.Popen',FailedCli)
    receipt=run_container(ws,'busybox@sha256:'+'b'*64,['false'],approved=True)
    assert receipt.status=='cleanup-unverifiable' and receipt.exit_code==-1
    assert journal_census(ws.root)['status']=='blocked-unverified-container'


def test_unwritable_evidence_preserves_started_journal(tmp_path,monkeypatch):
    ws=space(tmp_path)
    raw=json.dumps({'version':3,'workspace':'alpha',
        'expected_workspace_sha256':ws.manifest()['sha256'],
        'execution_nonce':'1'*32,'steps':[{'tool':'run',
        'image':'busybox@sha256:'+'a'*64,'argv':['false'],
        'timeout_seconds':5}]}).encode()
    plan,digest=parse_plan(raw)
    monkeypatch.setattr('agent_workspace.shutil.which',lambda _: '/usr/bin/docker')
    monkeypatch.setattr('agent_workspace.subprocess.Popen',FailedCli)
    with mock.patch('agent_host_census.record_unverified_docker_cleanup',
                    side_effect=OSError('synthetic disk-full')):
        with pytest.raises(CleanupUnverifiable):
            execute_plan(ws,plan,digest,approved_digest=digest)
    assert ApprovalJournal(ws).read(digest)['state']=='started'
    with pytest.raises(WorkspaceDenied,match='approval-already-consumed'):
        execute_plan(ws,plan,digest,approved_digest=digest)


def test_known_container_must_be_absent_on_same_daemon(tmp_path,monkeypatch):
    ws=space(tmp_path)
    cid='f'*64
    class KnownCli(FailedCli):
        def __init__(self,args,**kw):
            super().__init__(args,**kw)
            Path(args[args.index('--cidfile')+1]).write_text(cid)
    monkeypatch.setattr('agent_workspace.shutil.which',lambda _: '/usr/bin/docker')
    monkeypatch.setattr('agent_workspace.subprocess.Popen',KnownCli)
    calls=[]
    def docker(args,**kwargs):
        calls.append(args)
        if args[1]=='ps':
            return mock.Mock(returncode=0,stdout=b'')
        return mock.Mock(returncode=1)
    monkeypatch.setattr('agent_workspace.subprocess.run',docker)
    receipt=run_container(ws,'busybox@sha256:'+'b'*64,['false'],approved=True)
    assert receipt.exit_code==1
    assert receipt.status=='complete'
    assert journal_census(ws.root)['status']=='clear'
    assert [args[1] for args in calls]==['rm','ps']
    assert all('--filter' not in args or 'id='+cid in args for args in calls)


def test_container_still_visible_causes_fence(tmp_path,monkeypatch):
    ws=space(tmp_path)
    cid='e'*64
    class KnownCli(FailedCli):
        def __init__(self,args,**kw):
            super().__init__(args,**kw)
            Path(args[args.index('--cidfile')+1]).write_text(cid)
    monkeypatch.setattr('agent_workspace.shutil.which',lambda _: '/usr/bin/docker')
    monkeypatch.setattr('agent_workspace.subprocess.Popen',KnownCli)
    monkeypatch.setattr('agent_workspace.subprocess.run',
        lambda args,**kw: mock.Mock(returncode=0,stdout=cid.encode()+b'\n')
        if args[1]=='ps' else mock.Mock(returncode=0))
    receipt=run_container(ws,'busybox@sha256:'+'d'*64,['false'],approved=True)
    assert receipt.status=='cleanup-unverifiable'
    assert journal_census(ws.root)['status']=='blocked-unverified-container'
