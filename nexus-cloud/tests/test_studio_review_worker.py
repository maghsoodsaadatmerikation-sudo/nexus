import json
import sqlite3

import pytest

from studio_review_job_queue import ReviewJobQueue
from studio_review_worker import load_manifest, tick
from studio_workflow import Plan, review_plan
from studio_workflow_checkpoint import WorkflowCheckpointStore


def plan():
    return Plan.model_validate({"goal": "Review", "steps": [
        {"id": "find", "tool": "research", "description": "Find sources"},
    ]})


def setup(tmp_path):
    q = ReviewJobQueue(tmp_path / "queue.db")
    c = WorkflowCheckpointStore(tmp_path / "checkpoints.db")
    p = plan()
    c.create("job", p)
    q.submit("job", review_plan(p)["plan_sha256"], due=10, now=0)
    return q, c, p


def test_tick_validates_without_acknowledging_or_dispatching(tmp_path):
    q, c, p = setup(tmp_path)
    assert tick(q, c, {"job": p}, clock=lambda: 9)["status"] == "idle"
    result = tick(q, c, {"job": p}, clock=lambda: 10)
    assert result["status"] == "reviewed"
    assert result["checkpoint"]["acknowledged_count"] == 0
    assert result["checkpoint"]["status"] == "review_pending"
    assert result["execution_authorized"] is False
    assert "lease_token" not in result
    assert c.read("job", p)["revision"] == 0
    assert tick(q, c, {"job": p}, clock=lambda: 11)["status"] == "idle"


@pytest.mark.parametrize("kind", ["missing", "changed", "cancelled"])
def test_invalid_inputs_fail_closed(tmp_path, kind):
    q, c, p = setup(tmp_path)
    plans = {"job": p}
    if kind == "missing":
        plans.clear()
    elif kind == "changed":
        plans["job"] = p.model_copy(update={"goal": "Changed"})
    else:
        c.transition("job", p, expected_revision=0, operation_id="cancel",
                     action="cancel")
    result = tick(q, c, plans, clock=lambda: 10)
    assert result["status"] == "failed"
    assert result["execution_authorized"] is False
    assert "checkpoint" not in result


def test_transient_storage_error_retries(tmp_path, monkeypatch):
    q, c, p = setup(tmp_path)
    def unavailable(*args):
        raise sqlite3.OperationalError("private failure detail")
    monkeypatch.setattr(c, "read", unavailable)
    result = tick(q, c, {"job": p}, clock=lambda: 10)
    assert result["status"] == "queued"
    assert q.read("job")["due"] == 12
    assert "private failure detail" not in json.dumps(result)


def test_expired_lease_cannot_commit(tmp_path):
    q, c, p = setup(tmp_path)
    times = iter([10, 40])
    result = tick(q, c, {"job": p}, clock=lambda: next(times))
    assert result["status"] == "lease_lost"
    assert result["execution_authorized"] is False
    assert tick(q, c, {"job": p}, clock=lambda: 40)["status"] == "reviewed"


def test_manifest_bounds_and_duplicate_keys(tmp_path):
    path = tmp_path / "plans.json"
    path.write_text(json.dumps({"job": plan().model_dump()}))
    assert load_manifest(path)["job"] == plan()
    path.write_text('{"job": {}, "job": {}}')
    with pytest.raises(ValueError):
        load_manifest(path)
    path.write_bytes(b"x" * 65537)
    with pytest.raises(ValueError):
        load_manifest(path)
