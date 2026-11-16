"""Owner-only rootless plan and Unix socket admission: no implicit model authority."""
from __future__ import annotations
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from agent_chat_handoff import write_export
from agent_journal import ApprovalJournal
from agent_operator_service import OperatorServer, client
from agent_rootless_job import prepare_job, parse_job
from agent_workspace import Workspace, WorkspaceDenied

SOURCE = Path(__file__).resolve().parents[2] / 'scripts' / 'rootless-sandbox-probe.c'
CLI = Path(__file__).resolve().parents[2] / 'scripts' / 'nexus-rootless-job.py'


@pytest.fixture
def setup(tmp_path):
    if os.getuid() == 0:
        pytest.skip('rootless owner tests require an unprivileged user')
    root = tmp_path / 'private'; root.mkdir(mode=0o700)
    out = tmp_path / 'out'; out.mkdir(mode=0o700)
    binaries = tmp_path / 'binary'; binaries.mkdir(mode=0o700)
    exe = binaries / 'probe'
    build = subprocess.run(['cc', '-static', '-Os', str(SOURCE), '-o', str(exe)],
                           capture_output=True, text=True, timeout=35)
    assert build.returncode == 0, build.stderr[-400:]
    exe.chmod(0o500)
    sha = hashlib.sha256(exe.read_bytes()).hexdigest()
    ws = Workspace(root, 'alpha')
    ws.write('input.txt', b'sentinel')
    yield root, ws, out, exe, sha


def exported(ws, out, exe, sha, *, args=None):
    raw, review = prepare_job(ws, exe, sha, argv=args or [])
    path = write_export(out, f"nexus-plan-{review['plan_sha256'][:16]}.json", raw)
    return raw, review, path


def invoke(root, digest, action, path=None):
    return client(root, workspace='alpha', digest=digest, action='probe-'+action,
                  plan_path=str(path) if path is not None else None)


def start_service(root, *, rootless=True):
    service = OperatorServer(root, allow_rootless=rootless)
    listener = threading.Thread(target=service.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
    listener.start()
    return service, listener


def end_service(service, listener):
    service.shutdown(); listener.join(3); service.server_close()


def terminal(root, digest, *, limit=7):
    deadline=time.monotonic()+limit
    while time.monotonic()<deadline:
        result=invoke(root, digest, 'status')
        if result.get('journal_state') == 'finished':
            return result
        time.sleep(.02)
    raise AssertionError('rootless job remained unverified')


def test_job_parse_strict_rejects_replayable_or_tampered_json(setup):
    root,ws,out,exe,sha=setup
    raw,review,path=exported(ws,out,exe,sha,args=['--spam'])
    parsed,digest=parse_job(raw)
    assert digest==review['plan_sha256']
    assert parsed['workspace_sha256']==ws.manifest()['sha256']
    assert parse_job(raw)[1]==digest
    altered, altered_digest = parse_job(raw.replace(b'"alpha"', b'"beta"'))
    assert altered['workspace'] == 'beta' and altered_digest != digest
    for bad in [
                raw.replace(b'"nonce":',b'"nonce":"a","nonce":'),
                raw + b' ', raw.replace(b'"timeout_seconds":6', b'"timeout_seconds":true'),
                raw.replace(b'"schema":"nexus.rootless.operator-job.v1"',b'"schema":"wrong"'),
                raw.replace(b'"argv":',b'"escape":1,"argv":')]:
        with pytest.raises(WorkspaceDenied): parse_job(bad)
    assert b'input.txt' not in raw


def test_rootless_opt_in_required_and_tenant_cannot_enable(setup):
    root,ws,out,exe,sha=setup
    raw,review,path=exported(ws,out,exe,sha)
    with pytest.raises(WorkspaceDenied): OperatorServer(root, allow_container=False, allow_rootless=True)
    server,listener=start_service(root,rootless=False)
    try:
        assert invoke(root,review['plan_sha256'],'review',path)['status']=='denied'
        assert invoke(root,review['plan_sha256'],'start',path)['status']=='denied'
        assert invoke(root,review['plan_sha256'],'status')['status']=='denied'
        assert not (root/'.nexus-agent-alpha.journal').exists()
    finally:end_service(server,listener)


def test_owner_review_is_inert_stale_plan_and_modified_exe_refused(setup):
    root,ws,out,exe,sha=setup
    raw,review,path=exported(ws,out,exe,sha)
    server,listener=start_service(root)
    try:
        digest=review['plan_sha256']
        a=invoke(root,digest,'review',path)
        assert a['status']=='review' and a['summary']['review_required'] is True
        assert a['summary']['status']=='not-executed'
        assert 'input.txt' not in json.dumps(a) and str(exe) not in json.dumps(a)
        assert invoke(root,digest,'status')['status']=='not-found'
        ws.write('change.txt',b'external modification')
        assert invoke(root,digest,'start',path)['status']=='stale-plan-reapproval-required'
        assert invoke(root,digest,'status')['status']=='not-found'
        # The executable is separately bound; a changed binary is always rejected.
        exe.chmod(0o600); exe.write_bytes(exe.read_bytes()+b'x'); exe.chmod(0o500)
        assert invoke(root,digest,'start',path)['status']=='denied'
    finally:end_service(server,listener)


def test_durable_claim_stop_single_use_and_distinct_status_namespace(setup,monkeypatch):
    import agent_operator_service
    root,ws,out,exe,sha=setup
    raw,review,path=exported(ws,out,exe,sha)
    called=threading.Event()
    def fake_probe(*args,**kwargs):
        called.set()
        assert kwargs.get('expected_workspace_sha256')==review['workspace_sha256']
        assert kwargs['approved'] is True
        assert kwargs['cancel_event'].wait(4)
        return {'status':'cancelled','exit_code':-1}
    monkeypatch.setattr(agent_operator_service, 'run_probe', fake_probe)
    server,listener=start_service(root)
    try:
        digest=review['plan_sha256']
        assert invoke(root,digest,'start',path)['status']=='submitted-not-verified'
        assert called.wait(3)
        record=ApprovalJournal(ws).read(digest)
        assert record['state']=='started' and record['plan_version']==4
        assert record['execution_nonce']==parse_job(raw)[0]['nonce']
        assert invoke(root,digest,'start',path)['status']=='already-consumed'
        assert client(root,workspace='alpha',digest=digest,action='status')['status']=='denied'
        assert client(root,workspace='alpha',digest=digest,action='stop')['status']=='not-active'
        assert invoke(root,digest,'stop')['status']=='stop-requested-not-confirmed'
        final=terminal(root,digest)
        assert final['execution_status']=='cancelled' and final['journal_state']=='finished'
        assert final['authority']=='none' and final['origin']=='local-rootless-job'
        assert final['guest_output_included'] is False
        assert invoke(root,digest,'stop')['status']=='not-active'
        assert invoke(root,digest,'start',path)['status']=='already-consumed'
        assert ws.manifest()['sha256']==review['workspace_sha256']
    finally:end_service(server,listener)


def test_failed_sandbox_never_returns_success_or_replay(setup,monkeypatch):
    import agent_operator_service
    root,ws,out,exe,sha=setup
    raw,review,path=exported(ws,out,exe,sha)
    monkeypatch.setattr(agent_operator_service,'run_probe',lambda *a,**k: {'status':'sandbox-failed','exit_code':120})
    server,listener=start_service(root)
    try:
        digest=review['plan_sha256']
        assert invoke(root,digest,'start',path)['status']=='submitted-not-verified'
        report=terminal(root,digest)
        assert report['execution_status']=='execution-failed'
        assert report['verification']=='not-independent-attestation'
        assert invoke(root,digest,'start',path)['status']=='already-consumed'
    finally:end_service(server,listener)


def test_manual_operator_cli_private_prepare_and_review(setup):
    root,ws,out,exe,sha=setup
    cmd=[sys.executable,str(CLI),'prepare','--root',str(root),'--workspace','alpha',
         '--executable',str(exe),'--sha256',sha,'--out',str(out),'--arg','--spam']
    # argparse's --arg option may require --arg=--spam when starting with '-'.
    cmd[-2:] = ['--arg=--spam']
    prep=subprocess.run(cmd,capture_output=True,text=True,timeout=6)
    assert prep.returncode==0,prep.stderr
    data=json.loads(prep.stdout)
    digest=data['plan_sha256']
    path=Path(data['private_plan'])
    assert path.exists() and path.stat().st_mode&0o077==0
    server,listener=start_service(root)
    try:
        review=subprocess.run([sys.executable,str(CLI),'review','--root',str(root),
                               '--workspace','alpha','--digest',digest,'--plan',str(path)],
                              capture_output=True,text=True,timeout=6)
        assert review.returncode==0,review.stderr
        data=json.loads(review.stdout)
        assert data['status']=='not-executed' and data['authority']=='none'
        assert invoke(root,digest,'status')['status']=='not-found'
    finally:end_service(server,listener)


@pytest.mark.skipif(os.environ.get('NEXUS_ROOTLESS_REAL_JOB')!='true',reason='isolated real OS acceptance only')
def test_real_rootless_operator_job_fully_journaled(setup):
    root,ws,out,exe,sha=setup
    raw,review,path=exported(ws,out,exe,sha)
    server,listener=start_service(root)
    try:
        digest=review['plan_sha256']
        assert invoke(root,digest,'start',path)['status']=='submitted-not-verified'
        report=terminal(root,digest,limit=13)
        assert report['execution_status']=='complete',report
        assert report['workspace_sha256_after']==review['workspace_sha256']
        assert invoke(root,digest,'start',path)['status']=='already-consumed'
        assert not (ws.path/'pwned.txt').exists()
    finally:end_service(server,listener)


@pytest.mark.skipif(os.environ.get('NEXUS_ROOTLESS_REAL_JOB')!='true',reason='isolated real OS acceptance only')
def test_real_rootless_operator_stop_kills_guest_and_finishes_cancelled(setup):
    root,ws,out,exe,sha=setup
    raw,review,path=exported(ws,out,exe,sha,args=['--sleep'])
    server,listener=start_service(root)
    try:
        digest=review['plan_sha256']
        assert invoke(root,digest,'start',path)['status']=='submitted-not-verified'
        # Give the actual unshare process time to start, then send an
        # authenticated stop; it is not equivalent to terminal cancellation.
        time.sleep(.5)
        response=invoke(root,digest,'stop')
        assert response['status']=='stop-requested-not-confirmed',response
        report=terminal(root,digest,limit=12)
        assert report['execution_status']=='cancelled',report
        assert report['guest_output_included'] is False
        assert invoke(root,digest,'start',path)['status']=='already-consumed'
        assert not (ws.path/'pwned.txt').exists()
    finally:end_service(server,listener)
