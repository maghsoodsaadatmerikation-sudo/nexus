"""Fail-closed tenant host-admission contract (no root privileges required)."""
import os
import socket
import tempfile
import stat
from pathlib import Path

import pytest
from agent_tenant_boundary import (
    _private_root, _pid_owns_listening_socket, audit_tenants, cgroup_location, inspect_tenant,
    quota_values, read_proc_status, harden_tenant_daemon, require_dedicated_groups)
from agent_workspace import WorkspaceDenied
from agent_operator_service import TOKEN_NAME, SOCKET_NAME


def proof(uid, gid=None, *, nnp='1', caps='0000000000000000', uids=None, extra_groups=None):
    if gid is None: gid=uid
    return ('Name:\tnexus-tenant\nUid:\t'+(uids or (' '.join([str(uid)]*4)))+
            '\nGid:\t'+' '.join([str(gid)]*4)+'\nGroups:\t'+(str(gid) if extra_groups is None else extra_groups)+'\nNoNewPrivs:\t'+nnp+ '\nCapEff:\t'+caps+'\n')


def test_exact_process_identity_required():
    assert read_proc_status(proof(1234,5678))==(1234,5678)
    for value in [proof(0),proof(1234,nnp='0'),proof(1234,caps='0010'),
                  proof(1234,uids='1234 1234 0 1234'),proof(1234,gid=0),
                  proof(1234).replace('NoNewPrivs:\t1\n',''),
                  proof(1234).replace('Groups:\t1234\n',''),
                  proof(1234,extra_groups='1234 9999'),
                  proof(1234)+'Uid:\t1234 1234 1234 1234\n']:
        with pytest.raises(WorkspaceDenied): read_proc_status(value)


@pytest.mark.parametrize('memory,pids,cpu',[
    ('max','32','100000 100000'),('536870913','32','100000 100000'),
    ('536870912','max','100000 100000'),('536870912','129','100000 100000'),
    ('536870912','32','max 100000'),('536870912','32','0 100000'),
    ('536870912','32','200001 100000'),('536870912','32','100000 0'),
    ('1','32','100000 100000'),('536870912','7','100000 100000'),
    ('536870912','32','100000 100000 extra')])
def test_limits_reject_unsafe_values(memory,pids,cpu):
    with pytest.raises(WorkspaceDenied): quota_values(memory,pids,cpu)


def test_good_quota_and_invalid_cgroups():
    assert quota_values('268435456\n','64\n','100000 100000\n')=={
        'memory_bytes':268435456,'pids_max':64,'cpu_milli':1000}
    assert cgroup_location('0::/nexus.slice/nexus-tenant-123.scope\n')=='/nexus.slice/nexus-tenant-123.scope'
    for value in ['0::/','1:memory:/x','0::/x/../y','0::/x//y',
                  '0::/x\n0::/y','0::/x/$wrong']:
        with pytest.raises(WorkspaceDenied): cgroup_location(value)


def test_symlink_ancestor_and_open_root_rejected(tmp_path):
    d=tmp_path/'tenant';d.mkdir(mode=0o700)
    _private_root(d,os.getuid())
    alias=tmp_path/'alias';alias.symlink_to(d, target_is_directory=True)
    with pytest.raises(OSError): _private_root(alias,os.getuid())
    d.chmod(0o755)
    with pytest.raises(WorkspaceDenied): _private_root(d,os.getuid())
    d.chmod(0o700)
    unsafe=tmp_path/'writable-ancestor'
    unsafe.mkdir(mode=0o700)
    child=unsafe/'child';child.mkdir(mode=0o700)
    unsafe.chmod(0o777)
    with pytest.raises(WorkspaceDenied,match='writable-ancestor'):
        _private_root(child,os.getuid())


def fixtures(tmp_path, pid, uid=None, gid=None):
    uid=os.getuid() if uid is None else uid
    gid=os.getgid() if gid is None else gid
    root=tmp_path/f'private-{pid}';root.mkdir(mode=0o700)
    (root/TOKEN_NAME).write_text('f'*64)
    (root/TOKEN_NAME).chmod(0o600)
    s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    s.bind(str(root/SOCKET_NAME));os.chmod(root/SOCKET_NAME,0o600)
    proc=tmp_path/'proc'; proc.mkdir(exist_ok=True)
    pr=proc/str(pid);pr.mkdir();(pr/'status').write_text(proof(uid,gid))
    (pr/'cgroup').write_text(f'0::/nexus.slice/nexus-tenant-{uid}.scope\n')
    cg=tmp_path/'sys_cgroup';cg.mkdir(exist_ok=True)
    bound=cg/'nexus.slice'/f'nexus-tenant-{uid}.scope';bound.mkdir(parents=True,exist_ok=True)
    (bound/'memory.max').write_text('268435456\n')
    (bound/'pids.max').write_text('64\n')
    (bound/'cpu.max').write_text('100000 100000\n')
    return root,proc,cg,s


@pytest.mark.skipif(os.getuid()==0,reason='non-root peer fixture')
def test_single_real_private_user_fixture(tmp_path):
    root,proc,cg,s=fixtures(tmp_path,3001)
    try:
        evidence=inspect_tenant(root,3001,cgroup_base=cg,proc_base=proc)
        assert evidence.uid==os.getuid() and evidence.cpu_milli==1000
        root2,proc,cg,s2=fixtures(tmp_path,3002)
        try:
            with pytest.raises(WorkspaceDenied,match='shared-identity-or-resources'):
                audit_tenants([(root,3001),(root2,3002)],cgroup_base=cg,proc_base=proc)
        finally:s2.close()
    finally:s.close()


def test_privileged_host_is_denied_as_tenant(tmp_path):
    # A production tenant daemon refuses unrestricted root and lack of cgroup.
    with pytest.raises((WorkspaceDenied,OSError)):
        harden_tenant_daemon(tmp_path)


def test_tenant_count_gate():
    for tenants in [[],[('/tmp/single',123)], [('/tmp/x',12)]*33]:
        with pytest.raises(WorkspaceDenied):audit_tenants(tenants)


def test_process_must_own_active_unix_listener(tmp_path):
    path=tmp_path/'listener.sock'
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as listener:
        listener.bind(str(path));listener.listen(2)
        assert _pid_owns_listening_socket(os.getpid(),path)
        assert not _pid_owns_listening_socket(os.getpid()+999999,path)
    assert not _pid_owns_listening_socket(os.getpid(),path)


@pytest.mark.skipif(os.getuid()==0, reason='operator service requires nonroot')
def test_strict_tenant_operator_rejects_container_run_without_claiming_approval(tmp_path):
    from agent_chat_handoff import PROPOSAL_SCHEMA, prepare, write_export
    from agent_operator_service import OperatorServer
    from agent_workspace import Workspace

    root=tmp_path/'workspace';root.mkdir(mode=0o700)
    out=tmp_path/'out';out.mkdir(mode=0o700)
    ws=Workspace(root,'alpha');ws.write('in.txt',b'private')
    raw,review=prepare(ws,{'schema':PROPOSAL_SCHEMA,'workspace':'alpha','steps':[
        {'tool':'run','image':'busybox@sha256:'+'a'*64,
         'argv':['sh','-c','echo NOT_EXECUTED'], 'timeout_seconds':5}]})
    digest=review['plan_sha256']
    path=write_export(out, f'nexus-plan-{digest[:16]}.json',raw)
    with OperatorServer(root,allow_container=False) as server:
        base={'workspace':'alpha','digest':digest,'token':server._token,'plan_path':str(path)}
        meta=server.dispatch({'action':'review',**base},os.getuid())
        assert meta['status']=='review' and meta['summary']['status']=='not-executed'
        assert server.dispatch({'action':'start',**base},os.getuid())=={'status':'denied'}
        assert server.dispatch({'action':'status',**{k:v for k,v in base.items()
             if k!='plan_path'}},os.getuid())['status']=='not-found'
        assert ws.manifest()['sha256']==review['workspace_sha256']
        assert not (ws.path/'NOT_EXECUTED').exists()


@pytest.mark.skipif(os.getuid()==0,reason='operator service requires nonroot')
def test_strict_tenant_operator_keeps_safe_steps_available(tmp_path):
    from agent_chat_handoff import PROPOSAL_SCHEMA, prepare, write_export
    from agent_operator_service import OperatorServer
    from agent_workspace import Workspace
    from agent_journal import ApprovalJournal
    import time

    root=tmp_path/'workspace';root.mkdir(mode=0o700)
    out=tmp_path/'out';out.mkdir(mode=0o700)
    ws=Workspace(root,'alpha')
    raw,review=prepare(ws,{'schema':PROPOSAL_SCHEMA,'workspace':'alpha','steps':[
        {'tool':'write','path':'safe.txt','text':'owner-only'}]})
    digest=review['plan_sha256']
    plan=write_export(out, f'nexus-plan-{digest[:16]}.json',raw)
    with OperatorServer(root,allow_container=False) as server:
        args={'action':'start','workspace':'alpha','digest':digest,
              'token':server._token,'plan_path':str(plan)}
        assert server.dispatch(args,os.getuid())['status']=='submitted-not-verified'
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            try:
                receipt=ApprovalJournal(ws).read(digest)
            except FileNotFoundError:
                time.sleep(.01);continue
            if receipt['state']=='finished':break
            time.sleep(.01)
        assert receipt['state']=='finished' and receipt['result']=='complete'
        assert ws.read('safe.txt')==b'owner-only'


def test_strict_daemon_refuses_privileged_supplementary_groups():
    # Multiple nonroot groups are not harmless: one could own Docker.sock.
    require_dedicated_groups(61001, [])
    require_dedicated_groups(61001, [61001])
    for groups in ([61001, 61002], [61002], [0], [61001, 0], [61001, 61001, 61002], [True], ["61001"]):
        with pytest.raises(WorkspaceDenied,match='supplementary-groups-not-dedicated'):
            require_dedicated_groups(61001, groups)
    with pytest.raises(WorkspaceDenied):
        require_dedicated_groups(0, [])


@pytest.mark.skipif(os.getuid()==0, reason='requires a nonroot tenant operator')
@pytest.mark.parametrize('unsafe_step', [
    {'tool':'research','provider':'pypi','name':'requests'},
    {'tool':'package','output':'/tmp/nexus-tenant-public-archive.zip'},
    {'tool':'run','image':'busybox@sha256:'+'a'*64,
     'argv':['sh','-c','echo SHOULD_NOT_RUN'],'timeout_seconds':5},
])
def test_tenant_refuses_network_export_and_execution_before_journal(tmp_path, unsafe_step):
    from agent_chat_handoff import PROPOSAL_SCHEMA, prepare, write_export
    from agent_operator_service import OperatorServer
    from agent_workspace import Workspace
    from agent_journal import ApprovalJournal

    root=tmp_path/'tenant'; root.mkdir(mode=0o700)
    out=tmp_path/'private-out'; out.mkdir(mode=0o700)
    ws=Workspace(root,'alpha'); ws.write('private.txt',b'not public')
    raw,review=prepare(ws,{'schema':PROPOSAL_SCHEMA,'workspace':'alpha',
                          'steps':[{'tool':'write','path':'never-created.txt','text':'not executed'},
                                   unsafe_step]})
    digest=review['plan_sha256']
    path=write_export(out,f'nexus-plan-{digest[:16]}.json',raw)
    before=ws.manifest()['sha256']
    with OperatorServer(root,allow_container=False) as service:
        base={'workspace':'alpha','digest':digest,'token':service._token,
              'plan_path':str(path)}
        # Safe review is permitted but does not consume a one-time approval.
        assert service.dispatch({'action':'review',**base},os.getuid())['status']=='review'
        assert service.dispatch({'action':'start',**base},os.getuid())=={'status':'denied'}
        assert service.dispatch({'action':'status', **{k:v for k,v in base.items()
            if k!='plan_path'}},os.getuid())['status']=='not-found'
        assert not service._running
    assert ws.manifest()['sha256']==before
    assert not (ws.path/'never-created.txt').exists()
    with pytest.raises(FileNotFoundError):
        ApprovalJournal(ws).read(digest)


def test_restricted_tenant_tool_allowlist_is_closed():
    # A new privileged tool cannot silently become part of the tenant runtime.
    from engineering_agent import TOOLS
    approved={'read','write','edit','verify_sha256','search','preview_edit'}
    forbidden={'run','research','package'}
    assert set(TOOLS)==approved | forbidden
