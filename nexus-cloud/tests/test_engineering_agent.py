import hashlib
import json

import pytest
from agent_workspace import Workspace, WorkspaceDenied
from engineering_agent import execute_plan, parse_plan


@pytest.fixture
def ws(tmp_path):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    return Workspace(root, "example")


def makeplan(steps, workspace="example"):
    return json.dumps({"version": 1, "workspace": workspace, "steps": steps}).encode()


def test_plan_preview_digest_and_review_bound_execution(ws):
    steps = [{"tool": "write", "path": "src/main.py", "text": "print('ok')"},
             {"tool": "read", "path": "src/main.py"},
             {"tool": "verify_sha256", "path": "src/main.py", "expected_sha256": hashlib.sha256(b"print('ok')").hexdigest()}]
    plan, digest = parse_plan(makeplan(steps))
    with pytest.raises(WorkspaceDenied, match="approval"):
        execute_plan(ws, plan, digest, approved_digest="0"*64)
    assert not (ws.path / "src").exists()
    receipt = execute_plan(ws, plan, digest, approved_digest=digest)
    assert receipt.status == "complete" and receipt.completed_steps == 3
    assert receipt.results[2]["sha256"] == steps[2]["expected_sha256"]
    assert (ws.path / "src/main.py").read_text() == "print('ok')"


def test_plan_edit_invalidates_approval(ws):
    plan, digest = parse_plan(makeplan([{"tool": "write", "path": "hello", "text": "safe"}]))
    plan["steps"][0]["text"] = "changed"
    with pytest.raises(WorkspaceDenied, match="changed"):
        execute_plan(ws, plan, digest, approved_digest=digest)


@pytest.mark.parametrize("steps", [
    [{"tool": "execute_host_shell", "command": "whoami"}],
    [{"tool": "write", "path": "../escape", "text": "oops"}],
    [{"tool": "run", "image": "alpine:latest", "argv": ["true"], "timeout_seconds": 10}],
    [{"tool": "run", "image": "image@sha256:"+"a"*64, "argv": ["true"], "timeout_seconds": True}],
    [{"tool": "write", "path": "x", "text": "x", "extra": "unreviewed"}],
])
def test_invalid_plan_denied_before_actions(steps):
    with pytest.raises(WorkspaceDenied):
        parse_plan(makeplan(steps))


def test_failed_verification_stops_following_writes(ws):
    plan, digest = parse_plan(makeplan([
        {"tool": "write", "path": "a", "text": "value"},
        {"tool": "verify_sha256", "path": "a", "expected_sha256": "b"*64},
        {"tool": "write", "path": "b", "text": "must-not-be-written"},
    ]))
    result = execute_plan(ws, plan, digest, approved_digest=digest)
    assert result.status == "step-denied"
    assert (ws.path / "a").is_file() and not (ws.path / "b").exists()


def test_digest_canonical_across_whitespace_key_order():
    a = makeplan([{"tool": "read", "path": "a"}])
    b = b'{"steps":[{"path":"a","tool":"read"}],"workspace":"example","version":1}'
    assert parse_plan(a)[1] == parse_plan(b)[1]


def test_plan_no_changes_on_wrong_workspace(ws):
    plan, digest = parse_plan(makeplan([{"tool": "write", "path": "a", "text": "wrong"}], workspace="other"))
    with pytest.raises(WorkspaceDenied, match="wrong-workspace"):
        execute_plan(ws, plan, digest, approved_digest=digest)


def test_duplicate_plan_keys_rejected():
    raw = b'{"version":1,"workspace":"example","workspace":"other","steps":[{"tool":"read","path":"a"}]}'
    with pytest.raises(WorkspaceDenied, match="duplicate-plan-key"):
        parse_plan(raw)


def test_v2_plan_binds_workspace_state_before_mutation(ws):
    state = ws.manifest()["sha256"]
    payload = {"version": 2, "workspace": ws.name, "expected_workspace_sha256": state,
               "steps": [{"tool": "write", "path": "new", "text": "created"}]}
    plan, digest = parse_plan(json.dumps(payload).encode())
    result = execute_plan(ws, plan, digest, approved_digest=digest)
    assert result.status == "complete" and ws.read("new") == b"created"
    with pytest.raises(WorkspaceDenied, match="workspace-state-changed"):
        execute_plan(ws, plan, digest, approved_digest=digest)


def test_v2_stale_state_blocks_run_and_all_other_side_effects(ws, monkeypatch):
    state = ws.manifest()["sha256"]
    payload = {"version": 2, "workspace": ws.name, "expected_workspace_sha256": state,
               "steps": [{"tool": "write", "path": "must-not-exist", "text": "danger"},
                         {"tool": "run", "image": "repo@sha256:" + "a"*64, "argv": ["true"], "timeout_seconds": 4}]}
    plan, digest = parse_plan(json.dumps(payload).encode())
    ws.write("unreviewed-change", b"different")
    monkeypatch.setattr("engineering_agent.run_container", lambda *_args, **_kwargs: pytest.fail("unreviewed command"))
    with pytest.raises(WorkspaceDenied, match="reapproval"):
        execute_plan(ws, plan, digest, approved_digest=digest)
    assert not (ws.path / "must-not-exist").exists()


def test_v2_state_digest_changes_entire_plan_approval(ws):
    state = ws.manifest()["sha256"]
    payload = {"version": 2, "workspace": ws.name, "expected_workspace_sha256": state,
               "steps": [{"tool": "read", "path": "a"}]}
    plan, digest = parse_plan(json.dumps(payload).encode())
    plan["expected_workspace_sha256"] = "1"*64
    with pytest.raises(WorkspaceDenied, match="plan-changed"):
        execute_plan(ws, plan, digest, approved_digest=digest)


@pytest.mark.parametrize("raw", [
    b'{"version":2,"workspace":"example","steps":[{"tool":"read","path":"a"}]}',
    b'{"version":2,"workspace":"example","expected_workspace_sha256":"bad","steps":[{"tool":"read","path":"a"}]}',
    b'{"version":3,"workspace":"example","steps":[{"tool":"read","path":"a"}]}',
    b'{"version":2,"workspace":"example","expected_workspace_sha256":"' + b'0'*64 + b'","unexpected":true,"steps":[{"tool":"read","path":"a"}]}',
])
def test_v2_invalid_schema_denied(raw):
    with pytest.raises(WorkspaceDenied):
        parse_plan(raw)


def test_malformed_unicode_plan_denied_without_crash():
    invalid = ('{"version":1,"workspace":"example","steps":[{"tool":"write",'
               '"path":"a","text":"\\ud800"}]}').encode()
    with pytest.raises(WorkspaceDenied, match="encoding"):
        parse_plan(invalid)


def test_v2_cli_manifest_preview_execute_and_stale_rejection(ws, tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    tool = repo_root / "scripts/nexus-agent-workspace.py"
    planner = repo_root / "scripts/nexus-engineering-plan.py"
    base = [sys.executable, str(tool), "--root", str(ws.root), "--workspace", ws.name]
    snapshot = subprocess.run(base + ["manifest"], capture_output=True, text=True, check=True)
    state = json.loads(snapshot.stdout)["sha256"]
    raw = {"version": 2, "workspace": ws.name, "expected_workspace_sha256": state,
           "steps": [{"tool": "write", "path": "hello", "text": "NEXUS"}]}
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(raw))
    cmd = [sys.executable, str(planner), "--root", str(ws.root), "--plan", str(plan_file)]
    preview = json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)
    assert preview["current_workspace_sha256"] == state
    assert preview["plan_version"] == 2
    assert preview["state_matches"] is True
    digest = preview["plan_sha256"]
    applied = subprocess.run(cmd + ["--approve-digest", digest], capture_output=True, text=True)
    assert applied.returncode == 0, applied.stderr
    assert ws.read("hello") == b"NEXUS"
    stale = subprocess.run(cmd + ["--approve-digest", digest], capture_output=True, text=True)
    assert stale.returncode == 2
    assert json.loads(stale.stderr)["reason"] == "workspace-state-changed-reapproval-required"
