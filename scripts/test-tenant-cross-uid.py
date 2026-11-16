#!/usr/bin/env python3
"""Disposable two-UID Linux boundary test. No actual user/account creation.

Requires CI root solely to spawn two unprivileged worker identities; these
operators cannot acquire root and no host Docker daemon is contacted.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

if os.name != 'posix' or not hasattr(os, 'setresuid') or os.geteuid() != 0:
    raise SystemExit('cross-UID OS acceptance requires disposable root CI')
ORIGINAL_SOURCE = Path(__file__).resolve().parents[1]
SRC = ORIGINAL_SOURCE
UIDS = (61001, 61002)
PYTHON = sys.executable


def user(uid):
    def drop():
        os.setgroups([])
        os.setgid(uid)
        os.setuid(uid)
        os.umask(0o077)
    return drop


def invoke(uid, args, *, timeout=6):
    return subprocess.run([PYTHON, *map(str, args)], preexec_fn=user(uid),
                          capture_output=True, text=True, timeout=timeout,
                          env={'PATH': '/usr/bin:/bin', 'PYTHONPATH': str(SRC / 'nexus-cloud')},
                          cwd=str(SRC))


with tempfile.TemporaryDirectory(prefix='nexus-crossuid-') as temp:
    parent = Path(temp)
    parent.chmod(0o755)  # O_RDONLY|O_DIRECTORY root traversal requires read; children stay 0700.
    # Some CI checkout parents cannot be traversed by synthetic UIDs.
    # Copy only public source to a readable ephemeral directory, not secrets.
    SRC = parent / 'readable-source'
    SRC.mkdir(mode=0o755)
    for part in ('scripts', 'nexus-cloud'):
        shutil.copytree(ORIGINAL_SOURCE / part, SRC / part)
    roots = []
    outboxes = []
    for uid in UIDS:
        root = parent / ('user-' + str(uid))
        root.mkdir(mode=0o700); os.chown(root, uid, uid)
        out = parent / ('out-' + str(uid))
        out.mkdir(mode=0o700); os.chown(out, uid, uid)
        roots.append(root); outboxes.append(out)
    # Do not modify host accounts, persistent passwd, groups or cgroups.
    setup = '''import json,sys
from agent_workspace import Workspace
from agent_chat_handoff import prepare,PROPOSAL_SCHEMA,write_export
root,out,secret=sys.argv[1:4];ws=Workspace(root,'alpha')
ws.write('owner-only.txt',secret.encode())
raw,review=prepare(ws,{'schema':PROPOSAL_SCHEMA,'workspace':'alpha',
 'steps':[{'tool':'write','path':'result.txt','text':secret}]})
path=write_export(__import__('pathlib').Path(out),f"nexus-plan-{review['plan_sha256'][:16]}.json",raw)
print(json.dumps({'digest':review['plan_sha256'],'plan':str(path)}))'''
    plans=[]
    for idx,uid in enumerate(UIDS):
        result=invoke(uid,['-c',setup,roots[idx],outboxes[idx],'owner-secret-'+str(uid)])
        assert result.returncode==0, ('workspace-prep-failed',result.stderr[-400:])
        plans.append(json.loads(result.stdout))
    servers=[]
    try:
        for idx,uid in enumerate(UIDS):
            cmd=[PYTHON,str(SRC/'scripts/nexus-operator-service.py'),'serve','--root',str(roots[idx])]
            proc=subprocess.Popen(cmd,preexec_fn=user(uid),stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                  cwd=str(SRC),env={'PATH':'/usr/bin:/bin'})
            servers.append(proc)
            until=time.monotonic()+5
            while time.monotonic()<until and not (roots[idx]/'.nexus-operator.sock').exists():
                if proc.poll() is not None:break
                time.sleep(0.03)
            assert (roots[idx]/'.nexus-operator.sock').is_socket(), ('service-unavailable',proc.poll(),proc.stderr.read().decode()[:800] if proc.poll() is not None else '')
        # Strict multi-user entrypoint MUST refuse host setups without a
        # dedicated per-UID bounded cgroup; no socket may be created by it.
        for idx,uid in enumerate(UIDS):
            gate=invoke(uid,[SRC/'scripts/nexus-tenant-service.py','--root',roots[idx]])
            assert gate.returncode==2, 'unverified-multi-tenant-host-must-fail-closed'
        for source,uid in enumerate(UIDS):
            target=1-source
            result=invoke(uid,['-c','import pathlib,sys;pathlib.Path(sys.argv[1]).read_text()',
                               roots[target]/'alpha'/'owner-only.txt'])
            assert result.returncode!=0, 'cross-uid-private-file-was-read'
            result=invoke(uid,[SRC/'scripts/nexus-operator-service.py','status',
                               '--root',roots[target],'--workspace','alpha',
                               '--digest',plans[target]['digest']])
            assert result.returncode!=0, 'cross-uid-service-was-contacted'
        for idx,uid in enumerate(UIDS):
            command=[SRC/'scripts/nexus-operator-service.py','start',
                     '--root',roots[idx],'--workspace','alpha',
                     '--digest',plans[idx]['digest'],'--plan',plans[idx]['plan']]
            result=invoke(uid,command)
            assert (result.returncode==0 and
                    json.loads(result.stdout)['status']=='submitted-not-verified'), 'operator-approval-failed'
        for idx,uid in enumerate(UIDS):
            deadline=time.monotonic()+6
            while time.monotonic()<deadline:
                result=invoke(uid,[SRC/'scripts/nexus-operator-service.py','status',
                                   '--root',roots[idx],'--workspace','alpha',
                                   '--digest',plans[idx]['digest']])
                if result.returncode==0:
                    record=json.loads(result.stdout)
                    if record.get('journal_state')=='finished':break
                time.sleep(0.04)
            assert record['journal_state']=='finished' and record['execution_status']=='complete', 'owner-run-incomplete'
        for idx,uid in enumerate(UIDS):
            result=invoke(uid,['-c','import pathlib,sys;print(pathlib.Path(sys.argv[1]).read_text())',
                               roots[idx]/'alpha'/'result.txt'])
            assert result.returncode==0 and result.stdout.strip()=='owner-secret-'+str(uid), 'owner-result-not-isolated'
        print(json.dumps({'schema':'nexus.tenant-boundary.os-acceptance.v1',
                          'status':'PASS','tenant_uids_distinct':True,
                          'cross_uid_read_denied':True,'cross_uid_control_denied':True,
                          'separate_operator_execution':True,'strict_host_gate_denied_unprovisioned':True,
                          'docker_daemon_isolated':False,'production_attested':False,
                          'authority':'none'}))
    finally:
        for p in servers:
            if p.poll() is None:
                p.send_signal(signal.SIGINT)
        for p in servers:
            try:p.communicate(timeout=4)
            except subprocess.TimeoutExpired:
                p.kill();p.communicate(timeout=2)
