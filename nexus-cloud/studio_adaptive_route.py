"""Explicit task routing to reviewable Studio workflows, without dispatch."""
from __future__ import annotations

from typing import Literal

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

import studio_model as model
from studio_connections import operator_auth
from studio_peer_review import digest
from studio_research_evidence import clean
from studio_workflow import Plan, Step, ProgressReview, review_plan, review_progress
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}
Task = Literal["document_answer", "document_privacy", "manuscript_review",
               "research_synthesis", "paired_statistics", "general_chat"]
Privacy = Literal["device_only", "studio_only", "provider_allowed"]
Quality = Literal["extractive", "draft", "critique", "comparative"]
Slot = Literal["primary", "secondary", "tertiary"]


class RouteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    task: Task
    goal: str = Field(min_length=1, max_length=1000)
    privacy: Privacy = "studio_only"
    quality: Quality = "extractive"
    preferred_slot: Slot = "primary"
    document_count: int = Field(default=0, ge=0, le=3)


class RouteProgress(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    request: RouteRequest
    route_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    acknowledged: list[str] = Field(default_factory=list, max_length=12)
    cancelled: bool = False


def route(request, catalog):
    clean(request.goal, 1000)
    if request.task in ("document_answer", "document_privacy"):
        if request.document_count == 0:
            raise ValueError("Document count required")
        if request.task == "document_privacy" and request.document_count != 1:
            raise ValueError("Privacy review accepts one document")
    elif request.document_count:
        raise ValueError("Document count unsupported for this task")
    if request.task != "document_answer" and request.quality != "extractive":
        raise ValueError("Quality tiers apply only to document answers")

    steps, handoffs, blockers = [], [], []
    def add(id, tool, description, endpoint=None, boundary="studio", slot=None):
        steps.append(Step(id=id, tool=tool, description=description,
                          depends_on=[steps[-1].id] if steps else []))
        handoffs.append({"step_id": id, "review_endpoint": endpoint,
                         "boundary": boundary, "model_slot": slot,
                         "automatic_dispatch": False})

    # Server routes are not proof of device-local execution. Fail closed.
    if request.privacy == "device_only":
        blockers.append("device_execution_not_assessed")
        add("local_review", "human_review", "Select an independently verified device-local tool.",
            boundary="human")
    elif request.task == "document_answer":
        add("extract", "analysis", "Review supported document extraction.",
            "/studio/api/documents/extraction/review")
        add("retrieve", "research", "Review lexical search and approve selected excerpts.",
            "/studio/api/documents/search/review")
        add("evidence", "research", "Build the exact source evidence bundle.",
            "/studio/api/documents/evidence")
        if request.quality != "extractive":
            if request.privacy != "provider_allowed":
                blockers.append("external_provider_disclosure_not_allowed")
            else:
                slots = [s for s in ("primary", "secondary", "tertiary") if s in catalog]
                slots.sort(key=lambda s: (s != request.preferred_slot,
                                         ("primary", "secondary", "tertiary").index(s)))
                required = 2 if request.quality == "comparative" else 1
                if len(slots) < required:
                    blockers.append("insufficient_configured_model_slots")
                else:
                    chosen = slots[0]
                    add("generate", "writing", "Review exact provider payload and separately consent to generation.",
                        "/studio/api/documents/generation/review", "provider", chosen)
                    if request.quality in ("critique", "comparative"):
                        reviewers = slots[:required] if required == 2 else [chosen]
                        for i, slot in enumerate(reviewers):
                            add(f"critique_{i+1}", "analysis", "Review draft and separately consent to model critique.",
                                "/studio/api/documents/critique/review", "provider", slot)
                        if required == 2:
                            add("compare", "analysis", "Compare compatible critique receipts without a new model call.",
                                "/studio/api/documents/critique/comparison")
                        add("uncertainty", "analysis", "Inventory unresolved evidence and interpretation limits.",
                            "/studio/api/documents/metacognition")
        add("final_review", "human_review", "Review relevance, omissions and limitations before use.", boundary="human")
    elif request.task == "document_privacy":
        add("privacy", "analysis", "Inspect DOCX package metadata and review any proposed reset.",
            "/studio/api/documents/privacy/review")
        add("redaction", "writing", "Review explicit plaintext redaction rules if needed.",
            "/studio/api/research/anonymization/review")
        add("final_review", "human_review", "Inspect the actual output and remaining identity risks.", boundary="human")
    elif request.task == "manuscript_review":
        add("manuscript", "writing", "Check a manuscript against its research synthesis.",
            "/studio/api/research/manuscript-review")
        add("peer_review", "analysis", "Review research and structural issues.",
            "/studio/api/research/peer-review")
        add("journal", "research", "Compare supplied journal policies, if available.",
            "/studio/api/research/journal-review")
        add("final_review", "human_review", "Verify journal rules and scientific integrity.", boundary="human")
    elif request.task == "research_synthesis":
        add("evidence", "research", "Review supplied research cards and claim assessments.",
            "/studio/api/research/evidence-review")
        add("reasoning", "analysis", "Review source design and limitations.",
            "/studio/api/research/reasoning-review")
        add("graph", "analysis", "Build a claim graph from reviewed reasoning.",
            "/studio/api/research/knowledge-graph")
        add("conflicts", "analysis", "Review caller-reported conflicts and scope.",
            "/studio/api/research/conflict-review")
        add("uncertainty", "analysis", "Inventory unresolved research uncertainties.",
            "/studio/api/research/uncertainty-review")
        add("perspectives", "analysis", "Review competing perspectives.",
            "/studio/api/research/perspective-review")
        add("critique", "writing", "Check a structured draft against reviewed evidence.",
            "/studio/api/research/draft-critique")
        add("synthesis", "writing", "Build an explicitly provisional synthesis.",
            "/studio/api/research/synthesis")
        add("final_review", "human_review", "Independently verify source support.", boundary="human")
    elif request.task == "paired_statistics":
        add("analysis", "analysis", "Review paired observations and reported assumptions.",
            "/studio/api/statistics/paired/review")
        add("final_review", "human_review", "Interpret conditional results and verify assumptions.", boundary="human")
    else:
        if request.privacy != "provider_allowed":
            blockers.append("external_provider_disclosure_not_allowed")
        else:
            slots = [s for s in ("primary", "secondary", "tertiary") if s in catalog]
            if not slots:
                blockers.append("no_configured_model_slot")
            else:
                chosen = request.preferred_slot if request.preferred_slot in slots else slots[0]
                add("model", "writing", "Review exact model context and consent separately.",
                    "/studio-api/model-plan", "provider", chosen)
        add("final_review", "human_review", "Review available options and any response.", boundary="human")
    workflow = review_plan(Plan(goal=request.goal, steps=steps))
    # Bind configured provider identities only when a proposed provider step
    # references them. This is not a liveness or cost claim.
    referenced = {row["model_slot"] for row in handoffs if row["model_slot"] is not None}
    configurations = {slot: model.configuration_id(catalog[slot]) for slot in sorted(referenced)}
    data = {
        "request": request.model_dump(), "workflow": workflow, "handoffs": handoffs,
        "blockers": blockers, "configuration_ids": configurations,
    }
    return {
        **data, "schema_version": 1,
        "route_sha256": digest(b"nexus-adaptive-route-v1", data),
        "status": "requested_route_unavailable" if blockers else "review_only",
        "limitations": [
            "Task and privacy are caller-selected, not inferred from prose.",
            "Handoffs identify review APIs, not executable requests or completed steps.",
            "Provider eligibility is configured compatibility, not verified availability or quality.",
            "Every actual operation needs its own input validation and consent where applicable.",
            "Acknowledgments are caller reported, not proof of execution.",
        ],
        "provider_contact_attempted": False, "automatic_dispatch": False,
        "execution_authorized": False,
    }


def progress(request, catalog):
    reviewed = route(request.request, catalog)
    if request.route_sha256 != reviewed["route_sha256"]:
        raise ValueError("Stale route")
    workflow = reviewed["workflow"]
    checked = review_progress(ProgressReview(
        plan=Plan.model_validate(workflow["plan"]), plan_sha256=workflow["plan_sha256"],
        acknowledged=request.acknowledged, cancelled=request.cancelled))
    return {
        "route_sha256": reviewed["route_sha256"], "progress": checked,
        "route_blockers": reviewed["blockers"],
        "next_review_handoffs": [h for h in reviewed["handoffs"]
                                 if h["step_id"] in checked["ready_for_review"]],
        "requested_task_completion_verified": False, "execution_authorized": False,
        "automatic_dispatch": False,
    }


def register(app):
    async def parse(request, schema, fn):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=16384, timeout_seconds=10.0,
            too_large_detail="Adaptive route request too large",
            timeout_detail="Adaptive route request timed out", timeout_status=408)
        try:
            data = schema.model_validate_json(body)
            result = fn(data, model.read_model_catalog())
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid or stale adaptive route", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)

    @app.post("/studio/api/workflow/adaptive/review")
    async def review_endpoint(request: Request):
        return await parse(request, RouteRequest, route)

    @app.post("/studio/api/workflow/adaptive/progress")
    async def progress_endpoint(request: Request):
        return await parse(request, RouteProgress, progress)
