"""Operator-only lock, race and execution provenance regression tests."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from agent_workspace import Workspace, WorkspaceDenied
from engineering_agent import execute_plan, parse_plan


@pytest.fixture
def ws(tmp_path):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    return Workspace(root, "trial")


def plan(ws, steps):
    payload = {"version": 2, "workspace": ws.name,
               "expected_workspace_sha256": ws.manifest()["sha256"], "steps": steps}
    return parse_plan(json.dumps(payload).encode())


def test_lock_file_is_outside_content_and_stays_stable(ws):
    ws.write("src/hello.py", b"print('ok')", create_parents=True)
    initial = ws.manifest()
    with ws.operation_lock():
        assert (ws.root / ".nexus-agent-trial.lock").is_file()
        assert ws.manifest() == initial
    assert ws.manifest() == initial
    assert (ws.root / ".nexus-agent-trial.lock").stat().st_mode & 0o077 == 0


def test_cross_process_plan_denied_while_workspace_busy(ws):
    planner = Path(__file__).resolve().parents[2] / "scripts/nexus-engineering-plan.py"
    p, digest = plan(ws, [{"tool": "write", "path": "not-written", "text": "no"}])
    planfile = ws.root / "plan.json"
    planfile.write_text(json.dumps(p))
    with ws.operation_lock():
        result = subprocess.run([sys.executable, str(planner), "--root", str(ws.root),
                                 "--plan", str(planfile), "--approve-digest", digest],
                                capture_output=True, text=True, timeout=8)
        assert result.returncode == 2
        assert json.loads(result.stderr)["reason"] == "workspace-busy"
    assert not (ws.path / "not-written").exists()


def test_cross_process_direct_cli_denied_while_plan_lock_held(ws, tmp_path):
    cli = Path(__file__).resolve().parents[2] / "scripts/nexus-agent-workspace.py"
    supplied = tmp_path / "payload"
    supplied.write_bytes(b"do not write")
    with ws.operation_lock():
        result = subprocess.run([sys.executable, str(cli), "--root", str(ws.root),
                                 "--workspace", ws.name, "write", "blocked",
                                 "--from-file", str(supplied)],
                                capture_output=True, text=True, timeout=8)
        assert result.returncode == 2
        assert json.loads(result.stderr)["reason"] == "workspace-busy"
    assert not (ws.path / "blocked").exists()


def test_approval_receipt_binds_before_and_after_manifest(ws):
    original = ws.manifest()["sha256"]
    p, digest = plan(ws, [{"tool": "write", "path": "proof.txt", "text": "hello"},
                          {"tool": "verify_sha256", "path": "proof.txt",
                           "expected_sha256": hashlib.sha256(b"hello").hexdigest()}])
    receipt = execute_plan(ws, p, digest, approved_digest=digest)
    assert receipt.status == "complete" and receipt.completed_steps == 2
    assert receipt.workspace_sha256_before == original
    assert receipt.workspace_sha256_after == ws.manifest()["sha256"]
    assert receipt.workspace_sha256_before != receipt.workspace_sha256_after


def test_failure_receipt_shows_partial_mutation_without_rollback_claim(ws):
    p, digest = plan(ws, [{"tool": "write", "path": "kept", "text": "yes"},
                          {"tool": "verify_sha256", "path": "kept", "expected_sha256": "0" * 64},
                          {"tool": "write", "path": "skipped", "text": "no"}])
    receipt = execute_plan(ws, p, digest, approved_digest=digest)
    assert receipt.status == "step-denied"
    assert receipt.workspace_sha256_after == ws.manifest()["sha256"]
    assert receipt.workspace_sha256_before != receipt.workspace_sha256_after
    assert ws.read("kept") == b"yes"
    assert not (ws.path / "skipped").exists()


def test_command_causing_bad_workspace_state_never_claims_success(ws, monkeypatch):
    def bad_run(workspace, *args, **kwargs):
        (workspace.path / "trap").symlink_to("/etc/passwd")
        from agent_workspace import RunResult
        return RunResult(0, "", "", 1, "complete")
    monkeypatch.setattr("engineering_agent.run_container", bad_run)
    p, digest = plan(ws, [{"tool": "run", "image": "alpine@sha256:" + "a" * 64,
                           "argv": ["true"], "timeout_seconds": 10}])
    result = execute_plan(ws, p, digest, approved_digest=digest)
    assert result.status == "post-state-unverifiable"
    assert result.workspace_sha256_after is None


def test_malformed_lock_inode_denied(ws):
    lock = ws.root / ".nexus-agent-trial.lock"
    lock.symlink_to(ws.path)
    with pytest.raises(OSError):
        with ws.operation_lock():
            raise AssertionError("lock was not denied")


@pytest.mark.parametrize("invalid", [-1, 31, True, float("nan"), "three"])
def test_untrusted_lock_time_denied(ws, invalid):
    with pytest.raises(WorkspaceDenied, match="invalid-lock-timeout"):
        with ws.operation_lock(timeout_seconds=invalid):
            raise AssertionError("not allowed")
