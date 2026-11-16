from __future__ import annotations
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from agent_workspace import Workspace, WorkspaceDenied
from agent_research import ResearchDenied
from engineering_agent import execute_plan, parse_plan


@pytest.fixture
def ws(tmp_path):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    return Workspace(root, "project")


def test_code_search_casefold_line_number_and_binary_exclusion(ws):
    ws.write("src/main.rs", "fn main() {\n  // ÜBER status\n}\n".encode(), create_parents=True)
    ws.write(".env", b"NOT_A_SECRET=1")
    ws.write("binary.dat", b"foo\x00bar")
    result = ws.search("über")
    assert result["matches"] == [{"path": "src/main.rs", "line": 2, "excerpt": "  // ÜBER status"}]
    assert result["skipped_binary_files"] == 1
    assert ws.search("ÜBER", case_sensitive=True)["match_count"] == 1
    assert ws.search("über", case_sensitive=True)["match_count"] == 0
    assert ws.read("src/main.rs") == "fn main() {\n  // ÜBER status\n}\n".encode()


def test_preview_edit_does_not_write_and_provides_exact_diff(ws):
    ws.write("a.py", b"a = 1\nb = 2\n")
    info = ws.preview_edit("a.py", b"b = 2", b"b = 3")
    assert not info["applied"]
    assert "+b = 3" in info["diff"] and "-b = 2" in info["diff"]
    assert info["proposed_sha256"] == hashlib.sha256(b"a = 1\nb = 3\n").hexdigest()
    assert ws.read("a.py") == b"a = 1\nb = 2\n"


@pytest.mark.parametrize("old,new", [(b"missing", b"replacement"), (b"x", b"z")])
def test_invalid_preview_denied(ws, old, new):
    ws.write("a", b"xx")
    with pytest.raises(WorkspaceDenied):
        ws.preview_edit("a", old, new)


def test_safe_search_rejects_symlink_in_tree(ws):
    (ws.path / "escape").symlink_to("/tmp")
    with pytest.raises(WorkspaceDenied, match="manifest-rejects"):
        ws.search("hello")


def test_plan_search_and_preview_edit_are_read_only(ws):
    ws.write("src/main.py", b"assert True\n", create_parents=True)
    state = ws.manifest()["sha256"]
    raw = {"version": 2, "workspace": ws.name, "expected_workspace_sha256": state,
           "steps": [
               {"tool": "search", "query": "assert", "case_sensitive": False},
               {"tool": "preview_edit", "path": "src/main.py", "before": "True", "after": "False"},
           ]}
    plan, digest = parse_plan(json.dumps(raw).encode())
    receipt = execute_plan(ws, plan, digest, approved_digest=digest)
    assert receipt.status == "complete"
    assert receipt.results[0]["match_count"] == 1
    assert receipt.results[1]["proposed_sha256"] == hashlib.sha256(b"assert False\n").hexdigest()
    assert ws.manifest()["sha256"] == state


def test_exact_approval_required_before_networked_research(ws, monkeypatch):
    raw = {"version": 2, "workspace": ws.name, "expected_workspace_sha256": ws.manifest()["sha256"],
           "steps": [{"tool": "research", "provider": "pypi", "name": "httpx"}]}
    plan, digest = parse_plan(json.dumps(raw).encode())
    monkeypatch.setattr("engineering_agent.fetch_metadata", lambda *args: pytest.fail("network before approval"))
    with pytest.raises(WorkspaceDenied, match="approval"):
        execute_plan(ws, plan, digest, approved_digest="0"*64)
    ws.write("changed", b"X")
    with pytest.raises(WorkspaceDenied, match="state-changed"):
        execute_plan(ws, plan, digest, approved_digest=digest)


def test_research_receipt_is_explicitly_untrusted(ws, monkeypatch):
    raw = {"version": 2, "workspace": ws.name, "expected_workspace_sha256": ws.manifest()["sha256"],
           "steps": [{"tool": "research", "provider": "pypi", "name": "httpx"}]}
    plan, digest = parse_plan(json.dumps(raw).encode())
    monkeypatch.setattr("engineering_agent.fetch_metadata", lambda *args: {
        "version": "0.28.1", "provenance": "external-provider-metadata-unverified", "source_sha256": "a"*64})
    receipt = execute_plan(ws, plan, digest, approved_digest=digest)
    assert receipt.status == "complete"
    assert receipt.results[0]["provenance"] == "external-provider-metadata-unverified"


@pytest.mark.parametrize("step", [
    {"tool": "research", "provider": "pypi", "name": "http://evil"},
    {"tool": "research", "provider": "random-web", "name": "httpx"},
    {"tool": "research", "provider": "github-release", "name": "owner/repo/branch"},
    {"tool": "search", "query": "a\nb", "case_sensitive": False},
    {"tool": "search", "query": "ok", "case_sensitive": "no"},
    {"tool": "preview_edit", "path": "../escape", "before": "x", "after": "y"},
])
def test_invalid_tool_arguments_rejected_at_plan_parse(step):
    raw = {"version": 2, "workspace": "project", "expected_workspace_sha256": "a"*64, "steps": [step]}
    with pytest.raises((WorkspaceDenied, ResearchDenied)):
        parse_plan(json.dumps(raw).encode())


def test_cli_search_and_patch_preview(ws, tmp_path):
    ws.write("src/a.py", b"def greet():\n  return 'hi'\n", create_parents=True)
    tool = Path(__file__).resolve().parents[2] / "scripts/nexus-agent-workspace.py"
    cmd = [sys.executable, str(tool), "--root", str(ws.root), "--workspace", ws.name]
    result = subprocess.run(cmd+["search", "greet"], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["matches"][0]["line"] == 1
    before, after = tmp_path/"before.txt", tmp_path/"after.txt"
    before.write_text("'hi'")
    after.write_text("'hello'")
    result = subprocess.run(cmd+["preview-edit", "src/a.py", "--old-file", str(before), "--new-file", str(after)], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["applied"] is False
    assert ws.read("src/a.py") == b"def greet():\n  return 'hi'\n"


def test_cli_research_must_be_explicitly_approved_even_to_attempt_connection(ws):
    tool = Path(__file__).resolve().parents[2] / "scripts/nexus-agent-workspace.py"
    cmd = [sys.executable, str(tool), "--root", str(ws.root), "--workspace", ws.name]
    result = subprocess.run(cmd+["research", "--provider", "pypi", "--name", "httpx"], capture_output=True, text=True)
    assert result.returncode == 2
    assert json.loads(result.stderr)["reason"] == "research-requires-explicit-approval"


def test_large_text_preview_fails_before_quadratic_diff(ws):
    ws.write("many.txt", (b"line\n" * 2_100) + b"UNIQUE\n")
    with pytest.raises(WorkspaceDenied, match="preview-line-limit"):
        ws.preview_edit("many.txt", b"UNIQUE", b"changed")
