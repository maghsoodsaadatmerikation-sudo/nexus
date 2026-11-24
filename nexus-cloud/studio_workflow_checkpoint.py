"""Private SQLite review checkpoint store. No dispatch or execution authority."""
from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from studio_workflow import Plan, ProgressReview, review_plan, review_progress


class CheckpointConflict(ValueError):
    """Stale revision, changed plan, or incompatible operation replay."""


def _identifier(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", value):
        raise ValueError("Invalid checkpoint identifier")
    return value


class WorkflowCheckpointStore:
    """Operator-local store; caller must enforce ownership and private filesystem access."""

    def __init__(self, path: Path):
        self.path = Path(path)
        # No remote paths, client-provided paths, or in-memory database semantics.
        if not self.path.is_absolute() or not self.path.parent.is_dir():
            raise ValueError("Use an absolute path inside an existing private directory")
        with self._transaction() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS workflow_review_v1 (
                workflow_id TEXT PRIMARY KEY, plan_sha256 TEXT NOT NULL,
                revision INTEGER NOT NULL, acknowledged TEXT NOT NULL,
                cancelled INTEGER NOT NULL CHECK(cancelled IN (0, 1)))""")
            db.execute("""CREATE TABLE IF NOT EXISTS workflow_review_event_v1 (
                workflow_id TEXT NOT NULL REFERENCES workflow_review_v1(workflow_id),
                operation_id TEXT NOT NULL, event TEXT NOT NULL, revision INTEGER NOT NULL,
                PRIMARY KEY(workflow_id, operation_id), UNIQUE(workflow_id, revision))""")

    @contextmanager
    def _transaction(self):
        with closing(sqlite3.connect(self.path, timeout=3, isolation_level=None)) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("PRAGMA synchronous = FULL")
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.execute("COMMIT")
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise

    @staticmethod
    def _row(db, workflow_id, digest):
        row = db.execute(
            "SELECT * FROM workflow_review_v1 WHERE workflow_id = ?", (workflow_id,)
        ).fetchone()
        if row is None:
            raise KeyError("Unknown workflow")
        if row["plan_sha256"] != digest:
            raise CheckpointConflict("Changed plan identity")
        return row

    @staticmethod
    def _view(row, plan):
        result = review_progress(ProgressReview(
            plan=plan, plan_sha256=row["plan_sha256"],
            acknowledged=json.loads(row["acknowledged"]), cancelled=bool(row["cancelled"]),
        ))
        return {**result, "workflow_id": row["workflow_id"], "revision": row["revision"]}

    def create(self, workflow_id: str, plan: Plan) -> dict:
        workflow_id = _identifier(workflow_id)
        digest = review_plan(plan)["plan_sha256"]
        with self._transaction() as db:
            db.execute(
                "INSERT OR IGNORE INTO workflow_review_v1 VALUES (?, ?, 0, '[]', 0)",
                (workflow_id, digest),
            )
            return self._view(self._row(db, workflow_id, digest), plan)

    def read(self, workflow_id: str, plan: Plan) -> dict:
        workflow_id = _identifier(workflow_id)
        digest = review_plan(plan)["plan_sha256"]
        with self._transaction() as db:
            return self._view(self._row(db, workflow_id, digest), plan)

    def transition(self, workflow_id: str, plan: Plan, *, expected_revision: int,
                   operation_id: str, action: str, step_id: str | None = None) -> dict:
        workflow_id = _identifier(workflow_id)
        operation_id = _identifier(operation_id)
        if type(expected_revision) is not int or not 0 <= expected_revision <= 13:
            raise ValueError("Invalid revision")
        if action == "acknowledge":
            _identifier(step_id)
        elif action != "cancel" or step_id is not None:
            raise ValueError("Invalid checkpoint action")
        digest = review_plan(plan)["plan_sha256"]
        event = json.dumps([expected_revision, action, step_id], separators=(",", ":"))
        with self._transaction() as db:
            row = self._row(db, workflow_id, digest)
            state = self._view(row, plan)
            old = db.execute(
                "SELECT event, revision FROM workflow_review_event_v1 "
                "WHERE workflow_id = ? AND operation_id = ?", (workflow_id, operation_id)
            ).fetchone()
            if old is not None:
                if old["event"] != event:
                    raise CheckpointConflict("Operation identifier reused")
                return {**state, "replayed": True, "applied_revision": old["revision"]}
            if row["revision"] != expected_revision:
                raise CheckpointConflict("Stale revision")
            if state["status"] != "review_pending":
                raise CheckpointConflict("Terminal checkpoint")
            acknowledged = state["acknowledged"]
            if action == "acknowledge":
                if step_id not in state["ready_for_review"]:
                    raise CheckpointConflict("Step not ready")
                acknowledged = [*acknowledged, step_id]
            revision = expected_revision + 1
            db.execute(
                "UPDATE workflow_review_v1 SET revision=?, acknowledged=?, cancelled=? "
                "WHERE workflow_id=?", (revision, json.dumps(acknowledged),
                                        int(action == "cancel"), workflow_id)
            )
            db.execute(
                "INSERT INTO workflow_review_event_v1 VALUES (?, ?, ?, ?)",
                (workflow_id, operation_id, event, revision),
            )
            state = self._view(self._row(db, workflow_id, digest), plan)
            return {**state, "replayed": False, "applied_revision": revision}
