"""Operational readiness is not automatic execution authority or host attestation."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from agent_host_census import record_unverified_docker_cleanup
from agent_journal import ApprovalJournal
from agent_operator_pilot import readiness_snapshot, synthetic_smoke
from agent_workspace import Workspace, WorkspaceDenied

CLI = Path(__file__).resolve().parents[2] / "scripts" / "nexus-operator-pilot.py"


def setup_root(tmp_path):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    ws = Workspace(root, "alpha")
    return root, ws


@pytest.mark.skipif(os.getuid() == 0, reason="pilot runs only as a nonroot operator")
def test_preflight_clear_is_explicitly_not_production_attestation(tmp_path):
    root, ws = setup_root(tmp_path)
    before = sorted(x.name for x in root.iterdir())
    r = readiness_snapshot(root, workspace="alpha")
    assert r["status"] == "preflight-clear-not-attested"
    assert r["workspace_status"] == "existing"
    assert r["orphaned_processes_ruled_out"] is False
    assert r["production_ready"] is False and r["executed"] is False
    assert r["docker_inventory_status"] == "not-inspected"
    after = sorted(x.name for x in root.iterdir())
    assert set(after) - set(before) == {".nexus-agent-host-admission.lock"}
    assert not (root / ".nexus-operator.token").exists()


@pytest.mark.skipif(os.getuid() == 0, reason="pilot runs only as a nonroot operator")
def test_missing_workspace_is_not_created(tmp_path):
    root, _ = setup_root(tmp_path)
    r = readiness_snapshot(root, workspace="not-created")
    assert r["status"] == "blocked"
    assert r["workspace_status"] == "missing"
    assert not (root / "not-created").exists()


@pytest.mark.skipif(os.getuid() == 0, reason="pilot runs only as a nonroot operator")
def test_incomplete_journal_blocks_check(tmp_path):
    root, ws = setup_root(tmp_path)
    digest = hashlib.sha256(b"unfinished").hexdigest()
    with ws.operation_lock():
        ApprovalJournal(ws).claim(digest, version=3,
            workspace_before=ws.manifest()["sha256"], execution_nonce="a" * 32)
    r = readiness_snapshot(root, workspace="alpha")
    assert r["status"] == "blocked"
    assert r["unfinished_count"] == 1
    assert "approval-ledger-not-clear" in r["blockers"]
    assert r["production_ready"] is False


@pytest.mark.skipif(os.getuid() == 0, reason="pilot runs only as a nonroot operator")
def test_cleanup_uncertainty_blocks_check(tmp_path):
    root, _ = setup_root(tmp_path)
    record_unverified_docker_cleanup(root)
    r = readiness_snapshot(root)
    assert r["status"] == "blocked"
    assert r["docker_cleanup_unverified_count"] == 1
    assert r["orphaned_processes_ruled_out"] is False


@pytest.mark.skipif(os.getuid() == 0, reason="pilot runs only as a nonroot operator")
def test_docker_unverifiable_never_becomes_pass(tmp_path, monkeypatch):
    import agent_operator_pilot
    root, _ = setup_root(tmp_path)
    monkeypatch.setattr(agent_operator_pilot, "docker_inventory",
                        lambda: {"status": "unverifiable",
                                 "labelled_container_count": None})
    report = readiness_snapshot(root, inspect_docker=True)
    assert report["status"] == "blocked"
    assert report["docker_inventory_status"] == "unverifiable"
    assert report["production_ready"] is False


@pytest.mark.skipif(os.getuid() == 0, reason="pilot runs only as a nonroot operator")
def test_docker_empty_is_only_observation(tmp_path, monkeypatch):
    import agent_operator_pilot
    root, _ = setup_root(tmp_path)
    monkeypatch.setattr(agent_operator_pilot, "docker_inventory",
                        lambda: {"status": "no-labelled-containers-observed",
                                 "labelled_container_count": 0})
    report = readiness_snapshot(root, inspect_docker=True)
    assert report["status"] == "preflight-clear-not-attested"
    assert report["orphaned_processes_ruled_out"] is False
    assert report["host_attested"] is False


@pytest.mark.skipif(os.getuid() == 0, reason="pilot runs only as a nonroot operator")
def test_disposable_smoke_runs_real_operator_cycle():
    result = synthetic_smoke(approved=True)
    assert result["status"] == "disposable-operator-cycle-passed"
    assert result["journal_durable"] and result["one_use_replay_denied"]
    assert result["synthetic_steps_executed"] == 2
    assert result["guest_or_container_executed"] is False


def test_no_implicit_disposable_approval():
    with pytest.raises(WorkspaceDenied, match="explicit"):
        synthetic_smoke()
    p = subprocess.run([sys.executable, str(CLI), "smoke"],
                       capture_output=True, text=True, timeout=6)
    assert p.returncode == 2
    assert "denied" in p.stderr and not p.stdout


@pytest.mark.skipif(os.getuid() == 0, reason="pilot runs only as a nonroot operator")
def test_cli_check_and_smoke_modes(tmp_path):
    root, _ = setup_root(tmp_path)
    checked = subprocess.run([sys.executable, str(CLI), "check",
                              "--root", str(root), "--workspace", "alpha"],
                             capture_output=True, text=True, timeout=10)
    assert checked.returncode == 0, checked.stderr
    body = json.loads(checked.stdout)
    assert body["status"] == "preflight-clear-not-attested"
    accepted = subprocess.run([sys.executable, str(CLI), "smoke",
                               "--approve-disposable"],
                              capture_output=True, text=True, timeout=20)
    assert accepted.returncode == 0, accepted.stderr
    report = json.loads(accepted.stdout)
    assert report["status"] == "disposable-operator-cycle-passed"
    assert report["production_ready"] is False
    assert "token" not in accepted.stdout and "private-outbox" not in accepted.stdout


@pytest.mark.skipif(os.getuid() == 0, reason="pilot runs only as a nonroot operator")
def test_cli_refuses_missing_root_and_invalid_flags(tmp_path):
    absent = tmp_path / "absent"
    p = subprocess.run([sys.executable, str(CLI), "check", "--root", str(absent)],
                       capture_output=True, text=True, timeout=5)
    assert p.returncode == 2 and not absent.exists()
    bad = subprocess.run([sys.executable, str(CLI), "smoke", "--approve-disposable",
                          "--inspect-docker"], capture_output=True, text=True, timeout=5)
    assert bad.returncode == 2
