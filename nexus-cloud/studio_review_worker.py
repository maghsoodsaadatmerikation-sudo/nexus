"""Explicit single-tick worker for internal review jobs only."""
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path

from pydantic import ValidationError

from studio_review_job_queue import JobConflict, ReviewJobQueue
from studio_workflow import Plan, review_plan
from studio_workflow_checkpoint import CheckpointConflict, WorkflowCheckpointStore

MAX_MANIFEST_BYTES = 64 * 1024


def load_manifest(path: Path) -> dict[str, Plan]:
    """Read only an operator-selected bounded local file."""
    with path.open("rb") as stream:
        raw = stream.read(MAX_MANIFEST_BYTES + 1)
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError("Manifest too large")
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate manifest key")
            result[key] = value
        return result
    data = json.loads(raw, object_pairs_hook=unique_pairs)
    if not isinstance(data, dict) or len(data) > 32:
        raise ValueError("Invalid manifest")
    return {key: Plan.model_validate(value) for key, value in data.items()}


def tick(queue: ReviewJobQueue, checkpoints: WorkflowCheckpointStore,
         plans: dict[str, Plan], *, clock=None) -> dict:
    """Claim at most one job, validate its checkpoint, and record a queue outcome.

    A reviewed outcome is only a successful internal validation of supplied
    metadata; never a human approval, tool dispatch, or external execution.
    """
    clock = clock if clock is not None else lambda: int(time.time())
    lease = queue.claim(now=clock())
    if lease is None:
        return {"status": "idle", "execution_authorized": False}
    job_id = lease["job_id"]
    outcome = "failed"
    reason = "invalid_plan_or_checkpoint"
    checkpoint = None
    try:
        plan = plans.get(job_id)
        if plan is None:
            reason = "missing_plan"
        elif review_plan(plan)["plan_sha256"] != lease["plan_sha256"]:
            reason = "plan_digest_mismatch"
        else:
            state = checkpoints.read(job_id, plan)
            if state["status"] == "cancelled":
                reason = "checkpoint_cancelled"
            else:
                outcome = "reviewed"
                reason = "checkpoint_validated"
                checkpoint = {"revision": state["revision"], "status": state["status"],
                              "acknowledged_count": state["acknowledged_count"],
                              "total_steps": state["total_steps"]}
    except (KeyError, CheckpointConflict, ValidationError, ValueError):
        pass
    except sqlite3.OperationalError:
        outcome = "retry"
        reason = "checkpoint_temporarily_unavailable"
    try:
        final = queue.finish(job_id, lease["lease_token"], now=clock(), outcome=outcome)
    except JobConflict:
        return {"status": "lease_lost", "job_id": job_id, "execution_authorized": False}
    result = {"status": final["state"], "job_id": job_id, "reason": reason,
              "attempts": final["attempts"], "execution_authorized": False,
              "evidence": "internal_metadata_validation_only"}
    if checkpoint is not None and final["state"] == "reviewed":
        result["checkpoint"] = checkpoint
    return result


def main():
    parser = argparse.ArgumentParser(description="Process at most one internal review job")
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--checkpoints", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    plans = load_manifest(args.manifest)
    result = tick(ReviewJobQueue(args.queue), WorkflowCheckpointStore(args.checkpoints), plans)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
