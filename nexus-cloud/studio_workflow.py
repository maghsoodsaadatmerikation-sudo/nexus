"""Bounded, review-only workflow validation. Never invokes tools."""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_connections import operator_auth
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}
# These are proposed categories, not executable dispatch identifiers.
Tool = Literal["research", "analysis", "writing", "code", "connector", "human_review"]
BOUNDARIES = {
    "research": "Separate source and network review required.",
    "analysis": "Separate input and analysis review required.",
    "writing": "Review draft before export or transmission.",
    "code": "Separate exact-code and sandbox approval required.",
    "connector": "Separate target, operation and permission approval required.",
    "human_review": "Only a human may record the decision.",
}


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,31}$")
    tool: Tool
    description: str = Field(min_length=1, max_length=500)
    depends_on: list[str] = Field(default_factory=list, max_length=12)


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    goal: str = Field(min_length=1, max_length=1000)
    steps: list[Step] = Field(min_length=1, max_length=12)


def review_plan(plan: Plan) -> dict:
    """Reject ambiguous dependencies and return a deterministic review order."""
    ids = [step.id for step in plan.steps]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate step identifiers")
    for value in [plan.goal, *(s.description for s in plan.steps)]:
        if not value.strip() or any(0xD800 <= ord(c) <= 0xDFFF for c in value):
            raise ValueError("Invalid plan text")
    known = set(ids)
    for step in plan.steps:
        deps = step.depends_on
        if len(set(deps)) != len(deps) or step.id in deps or not set(deps) <= known:
            raise ValueError("Invalid step dependencies")
    order = []
    completed = set()
    while len(order) < len(ids):
        ready = next((s for s in plan.steps
                      if s.id not in completed and set(s.depends_on) <= completed), None)
        if ready is None:
            raise ValueError("Cyclic workflow dependencies")
        order.append(ready.id)
        completed.add(ready.id)
    canonical = json.dumps(plan.model_dump(), sort_keys=True, ensure_ascii=True,
                           separators=(",", ":")).encode("ascii")
    return {
        "schema_version": 1,
        "plan_sha256": hashlib.sha256(canonical).hexdigest(),
        "plan": plan.model_dump(),
        "review_order": order,
        "boundaries": {s.id: BOUNDARIES[s.tool] for s in plan.steps},
        "status": "review_only",
        "execution_authorized": False,
    }


class ProgressReview(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    plan: Plan
    plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    acknowledged: list[str] = Field(default_factory=list, max_length=12)
    cancelled: bool = False


def review_progress(progress: ProgressReview) -> dict:
    """Project supplied acknowledgments, not actual execution or authority."""
    reviewed = review_plan(progress.plan)
    if progress.plan_sha256 != reviewed["plan_sha256"]:
        raise ValueError("Stale plan identity")
    steps = {s.id: s for s in progress.plan.steps}
    acknowledged = set(progress.acknowledged)
    if len(acknowledged) != len(progress.acknowledged) or not acknowledged <= steps.keys():
        raise ValueError("Invalid acknowledgments")
    # Acknowledgment must be dependency-closed; the caller cannot skip prerequisites.
    if any(not set(steps[s].depends_on) <= acknowledged for s in acknowledged):
        raise ValueError("Missing prerequisite acknowledgment")
    order = reviewed["review_order"]
    ready = [] if progress.cancelled else [
        s for s in order if s not in acknowledged
        and set(steps[s].depends_on) <= acknowledged
    ]
    complete = len(acknowledged) == len(steps)
    return {
        "schema_version": 1,
        "plan_sha256": reviewed["plan_sha256"],
        "status": "cancelled" if progress.cancelled else (
            "all_acknowledged" if complete else "review_pending"
        ),
        "acknowledged": [s for s in order if s in acknowledged],
        "ready_for_review": ready,
        "blocked": [s for s in order if s not in acknowledged and s not in ready],
        "acknowledged_count": len(acknowledged),
        "total_steps": len(steps),
        "evidence": "caller_reported_only",
        "execution_authorized": False,
    }


def register(app):
    @app.post("/studio/api/workflow/review")
    async def workflow_review(request: Request):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=32768, timeout_seconds=10.0,
            too_large_detail="Workflow proposal too large",
            timeout_detail="Workflow proposal timed out", timeout_status=408,
        )
        try:
            plan = Plan.model_validate_json(body)
            result = review_plan(plan)
        except (ValidationError, ValueError):
            # Never reflect arbitrary user content in an error.
            raise HTTPException(422, "Invalid workflow proposal", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)


    @app.post("/studio/api/workflow/progress")
    async def workflow_progress(request: Request):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=32768, timeout_seconds=10.0,
            too_large_detail="Workflow progress too large",
            timeout_detail="Workflow progress timed out", timeout_status=408,
        )
        try:
            progress = ProgressReview.model_validate_json(body)
            result = review_progress(progress)
        except (ValidationError, ValueError):
            raise HTTPException(422, "Invalid workflow progress", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)
