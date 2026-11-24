"""Review-only workflow revision with conservative downstream invalidation."""
from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, ValidationError

from studio_connections import operator_auth
from studio_workflow import Plan, ProgressReview, review_plan, review_progress
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}


class RevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    previous: ProgressReview
    proposed: Plan


def review_revision(request: RevisionRequest) -> dict:
    """Compare exact plans; no checkpoint changes, approval, or execution."""
    previous = review_progress(request.previous)
    if previous["status"] == "cancelled":
        raise ValueError("Cancelled plan cannot be revised in place")
    proposed = review_plan(request.proposed)
    before = {step.id: step for step in request.previous.plan.steps}
    after = {step.id: step for step in request.proposed.steps}
    added = set(after) - set(before)
    removed = set(before) - set(after)
    changed = {key for key in before.keys() & after.keys()
               if before[key].model_dump() != after[key].model_dump()}
    goal_changed = request.previous.plan.goal != request.proposed.goal
    affected = set(after) if goal_changed else added | changed
    # Propagate invalidation across every downstream dependency.
    for step_id in proposed["review_order"]:
        if affected.intersection(after[step_id].depends_on):
            affected.add(step_id)
    old_ack = set(previous["acknowledged"])
    # Unaffected acknowledgments are only candidates for re-review.
    reusable = old_ack.intersection(after) - affected
    order = proposed["review_order"]
    return {
        "schema_version": 1,
        "previous_plan_sha256": previous["plan_sha256"],
        "proposed_plan_sha256": proposed["plan_sha256"],
        "status": "unchanged" if previous["plan_sha256"] == proposed["plan_sha256"]
                  else "revision_review_required",
        "goal_changed": goal_changed,
        "added": [key for key in order if key in added],
        "removed": [key for key in previous["acknowledged"] + [
            step.id for step in request.previous.plan.steps if step.id not in old_ack
        ] if key in removed],
        "changed": [key for key in order if key in changed],
        "affected": [key for key in order if key in affected],
        "invalidated_acknowledgments": [
            key for key in previous["acknowledged"] if key not in reusable
        ],
        "reusable_acknowledgment_candidates": [key for key in order if key in reusable],
        "proposed_review_order": order,
        "proposed_boundaries": proposed["boundaries"],
        "carried_acknowledgments": [],
        "execution_authorized": False,
        "evidence": "plan_comparison_only",
    }


def register(app):
    @app.post("/studio/api/workflow/revision-review")
    async def revision_endpoint(request: Request):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=65536, timeout_seconds=10.0,
            too_large_detail="Workflow revision too large",
            timeout_detail="Workflow revision timed out", timeout_status=408,
        )
        try:
            result = review_revision(RevisionRequest.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid workflow revision", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)
