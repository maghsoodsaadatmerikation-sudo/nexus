from concurrent.futures import ThreadPoolExecutor

import pytest

from studio_workflow import Plan
from studio_workflow_checkpoint import CheckpointConflict, WorkflowCheckpointStore


def plan():
    return Plan.model_validate({"goal": "Prepare report", "steps": [
        {"id": "write", "tool": "writing", "description": "Draft", "depends_on": ["find"]},
        {"id": "find", "tool": "research", "description": "Find sources"},
    ]})


def ack(store, p, revision=0, operation="op1", step="find"):
    return store.transition("work1", p, expected_revision=revision,
                            operation_id=operation, action="acknowledge", step_id=step)


def test_restart_and_replay(tmp_path):
    path = tmp_path / "review.db"
    p = plan()
    store = WorkflowCheckpointStore(path)
    assert store.create("work1", p)["revision"] == 0
    first = ack(store, p)
    assert first["ready_for_review"] == ["write"]
    assert first["execution_authorized"] is False
    reopened = WorkflowCheckpointStore(path)
    assert reopened.create("work1", p)["revision"] == 1
    second = ack(reopened, p, 1, "op2", "write")
    assert second["status"] == "all_acknowledged"
    replay = ack(reopened, p)
    assert replay["replayed"] is True
    assert replay["applied_revision"] == 1
    assert replay["revision"] == 2
    with pytest.raises(CheckpointConflict):
        ack(reopened, p, 1, "op1", "write")


def test_conflicts_do_not_mutate(tmp_path):
    store = WorkflowCheckpointStore(tmp_path / "review.db")
    p = plan()
    store.create("work1", p)
    with pytest.raises(CheckpointConflict):
        ack(store, p, step="write")
    with pytest.raises(CheckpointConflict):
        ack(store, p, revision=1)
    changed = p.model_copy(update={"goal": "Other goal"})
    with pytest.raises(CheckpointConflict):
        store.create("work1", changed)
    assert store.read("work1", p)["revision"] == 0
    assert ack(store, p)["revision"] == 1


def test_cancellation_survives_reopen(tmp_path):
    path = tmp_path / "review.db"
    p = plan()
    store = WorkflowCheckpointStore(path)
    store.create("work1", p)
    store.transition("work1", p, expected_revision=0, operation_id="cancel1", action="cancel")
    reopened = WorkflowCheckpointStore(path)
    assert reopened.read("work1", p)["status"] == "cancelled"
    assert reopened.read("work1", p)["ready_for_review"] == []
    with pytest.raises(CheckpointConflict):
        ack(reopened, p, 1)


def test_concurrent_updates_have_one_winner(tmp_path):
    path = tmp_path / "review.db"
    p = plan()
    store = WorkflowCheckpointStore(path)
    store.create("work1", p)

    def attempt(operation):
        try:
            return ack(store, p, operation=operation)["revision"]
        except CheckpointConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ["a", "b"]))
    assert sorted(map(str, results)) == ["1", "conflict"]
    assert store.read("work1", p)["revision"] == 1


def test_workflow_ids_and_plan_are_bound(tmp_path):
    store = WorkflowCheckpointStore(tmp_path / "review.db")
    p = plan()
    with pytest.raises(KeyError):
        store.read("unknown", p)
    with pytest.raises(ValueError):
        store.create("../escape", p)
    store.create("work1", p)
    store.create("work2", p)
    ack(store, p)
    assert store.read("work2", p)["revision"] == 0
