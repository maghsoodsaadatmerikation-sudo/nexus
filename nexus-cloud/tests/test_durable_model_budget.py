"""Fail-closed host-durable model quota regressions. No external model calls."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import subprocess
import sys

import pytest

from durable_model_budget import DurableModelRequestBudget, UnavailableModelRequestBudget
import studio_model as model


def private_state(tmp_path: Path) -> Path:
    root = tmp_path / "provider-budget"
    root.mkdir(mode=0o700)
    return root


def test_durable_budget_survives_worker_restart_and_shares_attempts(tmp_path):
    root = private_state(tmp_path)
    first = DurableModelRequestBudget(str(root), 2)
    assert first.reserve() is True
    assert first.snapshot() == {"limit": 2, "attempted": 1, "remaining": 1}
    first.close()
    second = DurableModelRequestBudget(str(root), 2)
    third = DurableModelRequestBudget(str(root), 2)
    try:
        assert second.snapshot()["remaining"] == 1
        assert third.reserve() is True
        assert second.snapshot() == {"limit": 2, "attempted": 2, "remaining": 0}
        assert third.reserve() is False
        assert second.reserve() is False
        assert (root / "model-attempts.counter").read_text() == "2\n"
        assert (root / "model-attempts.counter").stat().st_mode & 0o077 == 0
    finally:
        second.close()
        third.close()


def test_durable_budget_serializes_many_independent_worker_objects(tmp_path):
    root = private_state(tmp_path)
    def run(_):
        instance = DurableModelRequestBudget(str(root), 6)
        try:
            return instance.reserve()
        finally:
            instance.close()
    with ThreadPoolExecutor(max_workers=16) as pool:
        decisions = list(pool.map(run, range(80)))
    assert decisions.count(True) == 6
    assert decisions.count(False) == 74
    budget = DurableModelRequestBudget(str(root), 6)
    try:
        assert budget.snapshot()["attempted"] == 6
    finally:
        budget.close()


def test_separate_python_process_sees_durable_budget(tmp_path):
    root = private_state(tmp_path)
    counter = DurableModelRequestBudget(str(root), 1)
    assert counter.reserve()
    counter.close()
    script = ("from durable_model_budget import DurableModelRequestBudget; "
              "b = DurableModelRequestBudget(" + repr(str(root)) + ", 1); "
              "print('allowed' if b.reserve() else 'blocked'); b.close()")
    output = subprocess.run([sys.executable, "-c", script], check=True,
                            capture_output=True, text=True,
                            cwd=Path(__file__).resolve().parents[1])
    assert output.stdout.strip() == "blocked"


@pytest.mark.parametrize("bad_data", [b"secret", b"bad\n", b"-1\n",
                                       b"4097\n", b"1\n0\n", b"\n",
                                       b"9" * 20000])
def test_corruption_fails_closed_without_reset_or_overwrite(tmp_path, bad_data):
    root = private_state(tmp_path)
    counter = root / "model-attempts.counter"
    counter.write_bytes(bad_data)
    counter.chmod(0o600)
    budget = DurableModelRequestBudget(str(root), 5)
    try:
        assert budget.reserve() is False
        assert budget.snapshot() == {"limit": 5, "attempted": None, "remaining": 0}
        assert counter.read_bytes() == bad_data
    finally:
        budget.close()


def test_symlink_directory_is_denied(tmp_path):
    root = private_state(tmp_path)
    link = tmp_path / "symlink"
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(OSError):
        DurableModelRequestBudget(str(link), 3)


def test_symlink_counter_is_denied_without_clobber(tmp_path):
    root = private_state(tmp_path)
    outside = tmp_path / "outside"
    outside.write_text("private data")
    (root / "model-attempts.counter").symlink_to(outside)
    budget = DurableModelRequestBudget(str(root), 3)
    try:
        assert budget.reserve() is False
        assert budget.snapshot()["attempted"] is None
        assert outside.read_text() == "private data"
    finally:
        budget.close()


def test_world_readable_state_folder_fails_closed(tmp_path):
    root = private_state(tmp_path)
    root.chmod(0o755)
    with pytest.raises(PermissionError):
        DurableModelRequestBudget(str(root), 2)


def test_world_readable_or_multi_link_counter_fails_closed(tmp_path):
    root = private_state(tmp_path)
    counter = root / "model-attempts.counter"
    counter.write_text("1\n")
    counter.chmod(0o644)
    budget = DurableModelRequestBudget(str(root), 3)
    try:
        assert not budget.reserve()
        counter.chmod(0o600)
        extra = root / "second-hardlink"
        os.link(counter, extra)
        assert not budget.reserve()
        assert budget.snapshot()["attempted"] is None
    finally:
        budget.close()


def test_changed_directory_inode_fails_closed(tmp_path):
    root = private_state(tmp_path)
    b = DurableModelRequestBudget(str(root), 3)
    moved = tmp_path / "moved"
    root.rename(moved)
    root.mkdir(mode=0o700)
    try:
        assert b.reserve() is False
        assert b.snapshot()["attempted"] is None
    finally:
        b.close()


def test_io_error_fail_closed_and_does_not_refund_attempts(tmp_path, monkeypatch):
    root = private_state(tmp_path)
    b = DurableModelRequestBudget(str(root), 1)
    try:
        assert b.reserve()
        before = b.snapshot()
        def unavailable(_):
            raise OSError("synthetic storage failure")
        monkeypatch.setattr(b, "_commit_locked", unavailable)
        assert b.reserve() is False
        assert b.snapshot() == before
    finally:
        b.close()


def test_explicit_broken_durable_config_never_falls_back_to_restartable_guard(tmp_path, monkeypatch):
    absent = str(tmp_path / "not-created")
    monkeypatch.setenv("NEXUS_MODEL_BUDGET_DIR", absent)
    monkeypatch.setenv("NEXUS_MODEL_MAX_REQUESTS_PER_PROCESS", "3")
    b = model.create_model_request_budget()
    assert isinstance(b, UnavailableModelRequestBudget)
    assert b.limit == 3 and b.reserve() is False
    assert b.snapshot() == {"limit": 3, "attempted": None, "remaining": 0}


def test_private_durable_factory_uses_shared_store_and_detects_corruption(tmp_path, monkeypatch):
    root = private_state(tmp_path)
    monkeypatch.setenv("NEXUS_MODEL_BUDGET_DIR", str(root))
    monkeypatch.setenv("NEXUS_MODEL_MAX_REQUESTS_PER_PROCESS", "2")
    first = model.create_model_request_budget()
    assert isinstance(first, DurableModelRequestBudget)
    assert first.reserve() is True
    first.close()
    second = model.create_model_request_budget()
    try:
        assert second.snapshot() == {"limit": 2, "attempted": 1, "remaining": 1}
        (root / "model-attempts.counter").write_text("corrupt\n")
        assert second.reserve() is False
        assert second.snapshot()["attempted"] is None
    finally:
        second.close()


def test_durable_limit_change_never_resets_existing_counter(tmp_path):
    root = private_state(tmp_path)
    first = DurableModelRequestBudget(str(root), 5)
    for _ in range(3):
        assert first.reserve()
    first.close()
    smaller = DurableModelRequestBudget(str(root), 2)
    try:
        assert smaller.snapshot() == {"limit": 2, "attempted": 3, "remaining": 0}
        assert not smaller.reserve()
    finally:
        smaller.close()
