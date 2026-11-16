"""Private Unix control-plane acceptance; no Docker daemon or network required."""
import hashlib
import json
import os
import socket
import stat
import threading
import time
from pathlib import Path

import pytest
from agent_chat_handoff import PROPOSAL_SCHEMA, prepare, write_export
from agent_journal import ApprovalJournal
from agent_operator_service import OperatorServer, SOCKET_NAME, TOKEN_NAME, client
from agent_workspace import RunResult, Workspace, WorkspaceDenied


@pytest.fixture
def operator(tmp_path):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    ws = Workspace(root, "alpha")
    ws.write("hello.txt", b"unshared input")
    out = tmp_path / "outbox"
    out.mkdir(mode=0o700)
    server = OperatorServer(root)
    daemon = threading.Thread(target=server.serve_forever, kwargs={"poll_interval":0.01}, daemon=True)
    daemon.start()
    try:
        yield root, ws, out, server
    finally:
        server.shutdown()
        daemon.join(3)
        server.server_close()
        assert not (root / TOKEN_NAME).exists()
        assert not (root / SOCKET_NAME).exists()


def candidate(ws, out, steps):
    raw, report = prepare(ws, {"schema": PROPOSAL_SCHEMA, "workspace": ws.name, "steps": steps})
    digest = report["plan_sha256"]
    path = write_export(out, f"nexus-plan-{digest[:16]}.json", raw)
    return digest, path


def state(root, digest, *, action="status", plan=None, workspace="alpha"):
    return client(root, workspace=workspace, digest=digest, action=action,
                  plan_path=str(plan) if plan is not None else None)


def wait_terminal(root, digest, limit=5):
    deadline=time.monotonic()+limit
    while time.monotonic()<deadline:
        result=state(root,digest)
        if result.get("journal_state")=="finished":return result
        time.sleep(.02)
    raise AssertionError("durable finish not observed")


def test_private_socket_token_and_authorized_complete_receipt(operator):
    root,ws,out,server=operator
    sock=(root/SOCKET_NAME).lstat()
    tok=(root/TOKEN_NAME).lstat()
    assert stat.S_ISSOCK(sock.st_mode) and sock.st_mode & 0o077==0
    assert stat.S_ISREG(tok.st_mode) and tok.st_mode & 0o077==0
    digest,plan=candidate(ws,out,[{"tool":"read","path":"hello.txt"}])
    assert state(root,digest)=={"status":"not-found","plan_sha256":digest,"authority":"none"}
    ack=state(root,digest,action="start",plan=plan)
    assert ack["status"]=="submitted-not-verified"
    report=wait_terminal(root,digest)
    assert report["execution_status"]=="complete" and report["journal_state"]=="finished"
    assert report["steps"]==[{"index":0,"tool":"read","status":"completed"}]
    assert 'unshared input' not in json.dumps(report)
    assert state(root,digest,action="start",plan=plan)["status"]=="already-consumed"
    # A consumed approval must not be executed again.
    deadline=time.monotonic()+2
    while time.monotonic()<deadline:
        with server._state_lock:
            if not server._running:break
        time.sleep(.02)
    assert ApprovalJournal(ws).read(digest)["result"]=="complete"


def test_wrong_token_peer_and_malformed_json_never_execute(operator):
    root,ws,out,server=operator
    digest,path=candidate(ws,out,[{"tool":"write","path":"bad.txt","text":"NEVER_WRITTEN"}])
    authorized={"action":"start","workspace":"alpha","digest":digest,"plan_path":str(path),"token":"0"*64}
    assert server.dispatch(authorized,os.getuid())["status"]=="denied"
    authorized["token"]=server._token
    assert server.dispatch(authorized,os.getuid()+1)["status"]=="denied"
    for malformed in [b'{"action":"start","action":"start"}\n',b'{"token":NaN}\n',b'{not-json}\n',b'x'*17000+b'\n']:
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
            sock.settimeout(3);sock.connect(str(root/SOCKET_NAME));sock.sendall(malformed)
            assert b'"denied"' in sock.recv(1024)
    assert not (ws.path/"bad.txt").exists()


def test_mismatched_plan_and_foreign_outbox_fail_closed(operator,tmp_path):
    root,ws,out,server=operator
    digest,path=candidate(ws,out,[{"tool":"write","path":"bad.txt","text":"NEVER"}])
    assert state(root,"a"*64,action="start",plan=path)["status"]=="denied"
    assert state(root,digest,action="start",plan=path,workspace="other")["status"]=="denied"
    unprotected=tmp_path/"public";unprotected.mkdir(mode=0o755)
    moved=unprotected/path.name;moved.write_bytes(path.read_bytes())
    assert state(root,digest,action="start",plan=moved)["status"]=="denied"
    assert state(root,digest,action="start",plan=str(path)+".extra")["status"]=="denied"
    assert state(root,digest,action="stop")["status"]=="not-active"
    assert not (ws.path/"bad.txt").exists()


def test_operator_stop_terminates_cooperative_run_and_records_cancellation(operator,monkeypatch):
    root,ws,out,server=operator
    entered=threading.Event()
    def controlled_run(workspace,image,argv,*,approved,timeout_seconds,cancel_event=None):
        assert approved and cancel_event is not None
        entered.set()
        if not cancel_event.wait(timeout=3):
            raise AssertionError("stop-not-received")
        return RunResult(-1,"","",2,"cancelled")
    monkeypatch.setattr("engineering_agent.run_container", controlled_run)
    digest,path=candidate(ws,out,[{"tool":"run","image":"busybox@sha256:"+"b"*64,
                               "argv":["sh","-c","sleep 60"],"timeout_seconds":90},
                              {"tool":"write","path":"not-written.txt","text":"secret"}])
    assert state(root,digest,action="start",plan=path)["status"]=="submitted-not-verified"
    assert entered.wait(2)
    assert state(root,"c"*64,action="stop")["status"]=="not-active"
    assert state(root,digest,action="stop")["status"]=="stop-requested-not-confirmed"
    report=wait_terminal(root,digest)
    assert report["execution_status"]=="cancelled"
    assert report["steps"]==[{"index":0,"tool":"run","status":"cancelled"}]
    assert not (ws.path/"not-written.txt").exists()
    assert ApprovalJournal(ws).read(digest)["result"]=="cancelled"
    assert state(root,digest,action="stop")["status"]=="not-active"


def test_shutdown_does_not_grant_start_or_open_external_port(operator):
    root,ws,out,server=operator
    digest,path=candidate(ws,out,[{"tool":"read","path":"hello.txt"}])
    assert state(root,digest,action="unknown")["status"]=="denied"
    assert state(root,digest,action="start")["status"]=="denied"
    assert state(root,digest,action="status",plan=path)["status"]=="denied"
    assert not hasattr(server,"server_port")


def test_cancellation_before_first_step_is_durable_and_no_side_effect(tmp_path):
    from engineering_agent import execute_plan, parse_plan
    root=tmp_path/"onlyroot";root.mkdir(mode=0o700)
    ws=Workspace(root,"beta")
    raw,review=prepare(ws,{"schema":PROPOSAL_SCHEMA,"workspace":"beta","steps":[
        {"tool":"write","path":"never.txt","text":"private"}]})
    plan,digest=parse_plan(raw)
    cancel=threading.Event();cancel.set()
    result=execute_plan(ws,plan,digest,approved_digest=digest,cancel_event=cancel)
    assert result.status=="cancelled" and result.completed_steps==0
    assert not (ws.path/"never.txt").exists()
    assert ApprovalJournal(ws).read(digest)["result"]=="cancelled"
    with pytest.raises(WorkspaceDenied,match="approval-already-consumed"):
        execute_plan(ws,plan,digest,approved_digest=digest)


def test_cli_status_exports_studio_compatible_private_receipt(operator):
    import subprocess
    import sys
    root,ws,out,server=operator
    digest,path=candidate(ws,out,[{"tool":"read","path":"hello.txt"}])
    assert state(root,digest,action="start",plan=path)["status"]=="submitted-not-verified"
    wait_terminal(root,digest)
    cli=Path(__file__).resolve().parents[2]/"scripts/nexus-operator-service.py"
    def cmd(*extra):
        return subprocess.run([sys.executable,str(cli),"status","--root",str(root),"--workspace","alpha","--digest",digest,*extra],capture_output=True,text=True,timeout=5)
    raw=cmd()
    assert raw.returncode==0 and json.loads(raw.stdout)["schema"]=="nexus.engineering.chat-receipt.v1"
    assert "status" not in json.loads(raw.stdout)
    exported=cmd("--out",str(out))
    assert exported.returncode==0,exported.stderr
    path=Path(json.loads(exported.stdout)["chat_result"])
    assert path.name==f"nexus-result-{digest[:16]}.txt"
    assert path.stat().st_mode&0o077==0
    assert json.loads(path.read_text())==json.loads(raw.stdout)
    assert "unshared input" not in path.read_text()
    assert cmd("--out",str(out)).returncode==2
