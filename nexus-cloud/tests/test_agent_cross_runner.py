"""Phase 29 standalone negative tests for cross-runner synthetic recovery.

The separate GitHub jobs (workflow) are the actual transport-isolation proof.
These tests exercise local harness validation and strict refusal paths.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "test-operator-cross-runner.py"
SPEC = importlib.util.spec_from_file_location("nexus_cross_runner_tests", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


@pytest.fixture
def synthetic_source(tmp_path):
    if os.getuid() == 0:
        pytest.skip("operator transport acceptance must run as nonroot")
    scratch = tmp_path / "producer"
    scratch.mkdir(mode=0o700)
    report = module.produce(scratch)
    return scratch, report


def run_cli(*args):
    return subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, args)],
                          capture_output=True, text=True, timeout=15)


def test_explicit_approval_required_even_for_synthetic_source(tmp_path):
    root = tmp_path / "producer"
    root.mkdir(mode=0o700)
    reply = run_cli("produce", "--scratch", root)
    assert reply.returncode == 2
    assert "denied" in reply.stderr and not reply.stdout
    assert not list(root.iterdir())


@pytest.mark.skipif(os.getuid() == 0, reason="synthetic source requires nonroot")
def test_disposable_source_has_finished_receipt_and_no_credentials(synthetic_source):
    root, report = synthetic_source
    assert report["status"] == "cross-runner-synthetic-exported"
    assert report["production_ready"] is False
    assert report["publisher_authenticated"] is False
    assert report["finished_count"] == 1
    assert report["synthetic_only"] is True
    archive = root / "transfer" / "snapshot.zip"
    assert archive.is_file() and archive.stat().st_mode & 0o077 == 0
    assert module.snapshot.sha(archive.read_bytes()) == report["snapshot_sha256"]
    ws = module.Workspace(root / "source", module.WORKSPACE)
    assert ws.read("result.txt") == module.OUTPUT
    assert module.ApprovalJournal(ws).read(module.DIGEST)["state"] == "finished"
    assert not (root / "source" / ".nexus-operator.token").exists()


@pytest.mark.skipif(os.getuid() == 0, reason="restore requires nonroot")
def test_restored_receipt_replay_and_corruption_rejections(synthetic_source, tmp_path):
    root, evidence = synthetic_source
    dest = tmp_path / "receiver"
    dest.mkdir(mode=0o700)
    report = module.receive(dest, root / "transfer" / "snapshot.zip",
                            evidence["snapshot_sha256"],
                            evidence["workspace_sha256"])
    assert report["status"] == "cross-runner-synthetic-restore-passed"
    assert report["original_approval_replay_denied"]
    assert report["tampered_content_with_new_digest_denied"]
    assert report["wrong_archive_digest_denied"]
    assert report["overwrite_restored_root_denied"]
    assert report["jobs_restarted"] is False
    assert report["publisher_authenticated"] is False
    assert report["backup_encrypted"] is False


@pytest.mark.skipif(os.getuid() == 0, reason="restore requires nonroot")
def test_bad_independent_workspace_digest_denied_before_write(synthetic_source, tmp_path):
    root, evidence = synthetic_source
    dest = tmp_path / "receiver"
    dest.mkdir(mode=0o700)
    with pytest.raises(module.WorkspaceDenied, match="workspace-pin-mismatch"):
        module.receive(dest, root / "transfer" / "snapshot.zip",
                       evidence["snapshot_sha256"], "0"*64)
    assert list(dest.iterdir()) == []


@pytest.mark.skipif(os.getuid() == 0, reason="restore requires nonroot")
def test_bad_archive_hash_denied_before_write(synthetic_source, tmp_path):
    root, evidence = synthetic_source
    dest = tmp_path / "receiver"
    dest.mkdir(mode=0o700)
    with pytest.raises(module.WorkspaceDenied, match="snapshot-sha256-mismatch"):
        module.receive(dest, root / "transfer" / "snapshot.zip",
                       "0"*64, evidence["workspace_sha256"])
    assert list(dest.iterdir()) == []


@pytest.mark.skipif(os.getuid() == 0, reason="restore requires nonroot")
def test_nonempty_scratch_cannot_overwrite_user_data(synthetic_source, tmp_path):
    root, evidence = synthetic_source
    dest = tmp_path / "receiver"
    dest.mkdir(mode=0o700)
    existing = dest / "keep.txt"
    existing.write_text("existing")
    with pytest.raises(module.WorkspaceDenied, match="scratch-must-be-empty"):
        module.receive(dest, root / "transfer" / "snapshot.zip",
                       evidence["snapshot_sha256"], evidence["workspace_sha256"])
    assert existing.read_text() == "existing"


@pytest.mark.skipif(os.getuid() == 0, reason="restore requires nonroot")
def test_unknown_archive_symlink_denied(synthetic_source, tmp_path):
    root, evidence = synthetic_source
    dest = tmp_path / "receiver"
    dest.mkdir(mode=0o700)
    link = tmp_path / "archive-link.zip"
    link.symlink_to(root / "transfer" / "snapshot.zip")
    with pytest.raises(module.WorkspaceDenied, match="unsafe-archive"):
        module.receive(dest, link, evidence["snapshot_sha256"],
                       evidence["workspace_sha256"])
    assert list(dest.iterdir()) == []


@pytest.mark.skipif(os.getuid() == 0, reason="CLI requires nonroot")
def test_cli_explicit_synthetic_production_never_exports_source_paths(tmp_path):
    scratch = tmp_path / "producer"
    scratch.mkdir(mode=0o700)
    out = run_cli("produce", "--scratch", scratch, "--approve-synthetic-ci")
    assert out.returncode == 0, out.stderr
    parsed = json.loads(out.stdout)
    assert parsed["status"] == "cross-runner-synthetic-exported"
    assert parsed["production_ready"] is False
    assert parsed["authority"] == "none"
    assert "snapshot.zip" not in out.stdout
    assert str(tmp_path) not in out.stdout


@pytest.mark.skipif(os.getuid() == 0, reason="CLI requires nonroot")
def test_cli_rejects_receive_without_explicit_digest_and_approval(tmp_path):
    scratch = tmp_path / "receiver"
    scratch.mkdir(mode=0o700)
    reply = run_cli("receive", "--scratch", scratch, "--approve-synthetic-ci")
    assert reply.returncode == 2 and not reply.stdout
    assert not list(scratch.iterdir())
