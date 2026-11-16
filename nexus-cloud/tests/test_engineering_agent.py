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
