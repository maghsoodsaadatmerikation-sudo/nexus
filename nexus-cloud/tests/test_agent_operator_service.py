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


def test_operator_review_is_inert_and_does_not_consume_approval(operator):
    root, ws, out, server = operator
    steps = [{"tool": "write", "path": "PRIVATE-NAME.txt", "text": "PRIVATE-CONTENTS"},
             {"tool": "run", "image": "busybox@sha256:" + "a"*64,
              "argv": ["sh", "-c", "SECRET-COMMAND"], "timeout_seconds": 20},
             {"tool": "research", "provider": "pypi", "name": "requests"}]
    digest, plan = candidate(ws, out, steps)
    before = ws.manifest()["sha256"]
    report = state(root, digest, action="review", plan=plan)
    assert report["status"] == "review"
    assert report["summary"] == {
        "schema": "nexus.engineering.review.v1", "authority": "none",
        "plan_sha256": digest, "workspace_sha256": before, "workspace": "alpha",
        "plan_version": 3, "steps": [
            {"index": 0, "tool": "write", "risk": "writes-files"},
            {"index": 1, "tool": "run", "risk": "executes-container"},
            {"index": 2, "tool": "research", "risk": "network-metadata"}],
        "status": "not-executed", "review_required": True,
        "note": report["summary"]["note"],
    }
    serialized = json.dumps(report)
    for secret in ["PRIVATE-NAME", "PRIVATE-CONTENTS", "SECRET-COMMAND", "busybox@", str(plan), "requests"]:
        assert secret not in serialized
    assert ws.manifest()["sha256"] == before
    assert not (ws.path / "PRIVATE-NAME.txt").exists()
    assert state(root, digest)["status"] == "not-found"
    assert state(root, digest, action="review", plan=plan) == report


@pytest.mark.parametrize("action", ["review", "start"])
def test_stale_plan_cannot_be_approved_or_enqueued(operator, action):
    root, ws, out, server = operator
    digest, plan = candidate(ws, out, [{"tool": "write", "path": "should-not-exist.txt", "text": "PRIVATE"}])
    ws.write("independent.txt", b"unexpected external change")
    result = state(root, digest, action=action, plan=plan)
    assert result == {"status": "stale-plan-reapproval-required", "authority": "none"}
    assert state(root, digest)["status"] == "not-found"
    with server._state_lock:
        assert "alpha" not in server._running
    assert not (ws.path / "should-not-exist.txt").exists()


@pytest.mark.parametrize("action", ["review", "start"])
def test_review_and_start_refuse_already_consumed_approval(operator, action):
    root, ws, out, server = operator
    digest, plan = candidate(ws, out, [{"tool": "read", "path": "hello.txt"}])
    assert state(root, digest, action="start", plan=plan)["status"] == "submitted-not-verified"
    wait_terminal(root, digest)
    assert state(root, digest, action=action, plan=plan)["status"] == "already-consumed"


def test_review_never_creates_workspace_on_bad_workspace_id(operator):
    root, ws, out, server = operator
    digest, plan = candidate(ws, out, [{"tool": "read", "path": "hello.txt"}])
    assert state(root, digest, action="review", plan=plan, workspace="invented")["status"] == "denied"
    assert not (root / "invented").exists()


def test_operator_denies_symlink_in_ancestor_path(operator, tmp_path):
    root, ws, out, server = operator
    alias = tmp_path / "alias"
    alias.symlink_to(root.parent, target_is_directory=True)
    with pytest.raises((OSError, WorkspaceDenied)):
        client(alias / root.name, workspace="alpha", digest="a"*64, action="status")
    with pytest.raises((OSError, WorkspaceDenied)):
        OperatorServer(alias / root.name)


def test_review_cli_requires_private_plan_but_never_executes(operator):
    import subprocess
    import sys
    root, ws, out, server = operator
    digest, plan = candidate(ws, out, [{"tool": "write", "path": "not-yet.txt", "text": "PRIVATE-TEXT"}])
    cli = Path(__file__).resolve().parents[2] / "scripts/nexus-operator-service.py"
    cmd = [sys.executable, str(cli), "review", "--root", str(root), "--workspace", "alpha", "--digest", digest]
    missing = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    assert missing.returncode == 2
    report = subprocess.run([*cmd, "--plan", str(plan)], capture_output=True, text=True, timeout=5)
    assert report.returncode == 0, report.stderr
    assert json.loads(report.stdout)["schema"] == "nexus.engineering.review.v1"
    assert json.loads(report.stdout)["status"] == "not-executed"
    assert "PRIVATE-TEXT" not in report.stdout
    assert state(root, digest)["status"] == "not-found"
    assert not (ws.path / "not-yet.txt").exists()


def test_no_plan_file_status_and_stop_are_rejected(operator):
    root, ws, out, server = operator
    digest, plan = candidate(ws, out, [{"tool": "read", "path": "hello.txt"}])
    for action in ("status", "stop"):
        assert state(root, digest, action=action, plan=plan)["status"] == "denied"
    assert state(root, digest, action="review")["status"] == "denied"
    assert state(root, digest)["status"] == "not-found"


def test_handler_concurrency_capacity_does_not_grant_execution(operator):
    root, ws, out, server = operator
    digest, plan = candidate(ws, out, [{"tool": "write", "path": "never.txt", "text": "PRIVATE"}])
    # Exhaust capacity without occupying request-processing threads. A new
    # incoming local connection must be dropped rather than creating a worker.
    for _ in range(12):
        assert server._clients.acquire(blocking=False)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(2)
            sock.connect(str(root / SOCKET_NAME))
            try:
                received = sock.recv(1024)
            except ConnectionResetError:
                received = b""
            assert received == b""
        assert not (ws.path / "never.txt").exists()
    finally:
        for _ in range(12):
            server._clients.release()
    assert state(root, digest)["status"] == "not-found"


def test_operator_review_cli_exports_strict_studio_review(operator):
    import subprocess
    import sys
    root, ws, out, server = operator
    digest, plan = candidate(ws, out, [{"tool": "write", "path": "redacted.txt", "text": "PRIVATE_SECRET_42"}])
    cli = Path(__file__).resolve().parents[2] / "scripts/nexus-operator-service.py"
    cmd = [sys.executable, str(cli), "review", "--root", str(root), "--workspace", "alpha",
           "--digest", digest, "--plan", str(plan), "--out", str(out)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "exported" and response["authority"] == "none"
    exported = Path(response["chat_review"])
    assert exported.name == f"nexus-review-{digest[:16]}.txt"
    assert exported.stat().st_mode & 0o077 == 0
    report = json.loads(exported.read_text())
    assert set(report) == {"schema", "authority", "plan_sha256", "workspace_sha256", "workspace",
                           "plan_version", "steps", "status", "review_required", "note"}
    assert report["status"] == "not-executed" and report["review_required"] is True
    assert "PRIVATE_SECRET_42" not in exported.read_text() and "redacted.txt" not in exported.read_text()
    assert state(root, digest)["status"] == "not-found"
    assert not (ws.path / "redacted.txt").exists()
    # Check the exact saved object against the real Studio parser, not merely
    # a Python imitation of its JSON schema.
    js_core = Path(__file__).resolve().parents[2] / "web/studio-engineering.js"
    browser_parser = subprocess.run(["node", "-e",
        "const fs=require('node:fs');require(process.argv[1]);"
        "const v=NexusEngineering.inspect(fs.readFileSync(process.argv[2],'utf8'));"
        "if(v.kind!=='review'||v.state!=='not-executed'||v.authority!=='none')process.exit(3);"
        "process.stdout.write(JSON.stringify({kind:v.kind,steps:v.steps.length}));",
        str(js_core), str(exported)], capture_output=True, text=True, timeout=5)
    assert browser_parser.returncode == 0, browser_parser.stderr
    assert json.loads(browser_parser.stdout) == {"kind": "review", "steps": 1}
    # Repeated export cannot replace an earlier review file.
    repeated = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    assert repeated.returncode == 2


def test_operator_review_cli_cannot_export_stale_plan(operator):
    import subprocess
    import sys
    root, ws, out, server = operator
    digest, plan = candidate(ws, out, [{"tool": "write", "path": "never.txt", "text": "PRIVATE"}])
    ws.write("change.txt", b"workspace changed externally")
    cli = Path(__file__).resolve().parents[2] / "scripts/nexus-operator-service.py"
    args = [sys.executable, str(cli), "review", "--root", str(root), "--workspace", "alpha",
            "--digest", digest, "--plan", str(plan), "--out", str(out)]
    result = subprocess.run(args, capture_output=True, text=True, timeout=5)
    assert result.returncode == 2
    assert "stale-plan-reapproval-required" in result.stdout or "denied" in result.stderr
    assert not (out / f"nexus-review-{digest[:16]}.txt").exists()


@pytest.mark.parametrize("action", ["review", "start"])
def test_operator_refuses_nonprivate_plan_file_even_inside_private_outbox(operator, action):
    root, ws, out, server = operator
    digest, plan = candidate(ws, out, [{"tool": "write", "path": "not-written.txt", "text": "secret"}])
    plan.chmod(0o644)
    assert state(root, digest, action=action, plan=plan)["status"] == "denied"
    assert state(root, digest)["status"] == "not-found"
    assert not (ws.path / "not-written.txt").exists()
    plan.chmod(0o600)
    assert state(root, digest, action="review", plan=plan)["status"] == "review"


def test_reject_hardlinked_plan_without_consuming_approval(operator):
    root, ws, out, server = operator
    digest, plan = candidate(ws, out, [{"tool": "write", "path": "not-written.txt", "text": "secret"}])
    link = out / "second-link-to-plan.json"
    os.link(plan, link)
    assert state(root, digest, action="start", plan=plan)["status"] == "denied"
    assert state(root, digest)["status"] == "not-found"
    assert not (ws.path / "not-written.txt").exists()
