"""Traceable uncertainty register; no inferred probabilities or truth scores."""
from __future__ import annotations

import hashlib
import json

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_connections import operator_auth
from studio_research_conflicts import ConflictRequest, compare_claims
from studio_research_graph import graph
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}

# Fixed review prompts, not claims that a check has already been performed.
PROMPTS = {
    "reported_disagreement_requires_reconciliation": ("disagreement", "Inspect competing excerpts and their contexts."),
    "no_unambiguously_supporting_source_identity_reported": ("evidence", "Locate substantive evidence for the claim; preserve opposing findings."),
    "metadata_only_sources_not_substantive_evidence": ("evidence", "Retrieve and inspect substantive source text before drawing conclusions."),
    "supporting_source_design_unannotated": ("method", "Document the actual study design from the source."),
    "study_design_uncertain": ("method", "Check study design and what it can establish."),
    "applicability_unresolved": ("scope", "Compare the target population and study context."),
    "limitations_review_incomplete": ("method", "Review limitations, bias and alternative explanations."),
    "no_supporting_causal_design_reported": ("inference", "Investigate whether any supporting study can identify causal effects."),
    "causal_identification_not_verified": ("inference", "Independently examine causal assumptions, confounding and identification."),
    "out_of_sample_validation_not_verified": ("inference", "Inspect validation on genuinely independent data."),
    "association_does_not_establish_causation": ("inference", "Keep association distinct from a causal conclusion."),
    "hypothesis_not_established_finding": ("inference", "Specify what observations could test or refute the hypothesis."),
    "observation_not_generalizable_without_review": ("scope", "Review sampling, context and generalizability."),
}


class UncertaintyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    conflict_request: ConflictRequest
    conflict_review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def inventory(request: UncertaintyRequest):
    conflict = compare_claims(request.conflict_request)
    if conflict["conflict_review_sha256"] != request.conflict_review_sha256:
        raise ValueError("Stale conflict review")
    checked = graph(request.conflict_request.graph_request)
    entries = []

    def add(code, category, target, action, **details):
        key = json.dumps([code, target, details], sort_keys=True,
                         ensure_ascii=True, separators=(",", ":")).encode("ascii")
        entries.append({
            "id": "u-" + hashlib.sha256(key).hexdigest(),
            "code": code, "category": category, "target": target,
            "review_action": action, "status": "unresolved",
            **details,
        })

    for node in checked["nodes"]:
        if node["kind"] != "claim":
            continue
        target = [node["id"]]
        add("independent_verification_missing", "verification", target,
            "Independently inspect the original sources and claim interpretation.")
        for issue in node["issues"]:
            category, action = PROMPTS.get(issue, (
                "other", "Inspect the upstream review issue before drawing a conclusion."))
            add(issue, category, target, action)
    for edge in checked["edges"]:
        if not edge["from"].startswith("source:"):
            continue
        target = [edge["from"], edge["to"]]
        if edge["relation"] == "caller_reported_unassessed_or_unclear":
            add("source_stance_unresolved", "evidence", target,
                "Review whether the source addresses the particular claim.",
                source_indices=edge["source_indices"])
        if edge["metadata_only"]:
            add("source_content_missing", "evidence", target,
                "Metadata alone does not establish source findings.",
                source_indices=edge["source_indices"])
    for claim_id in conflict["unframed_claim_ids"]:
        add("claim_frame_missing", "scope", ["claim:" + claim_id],
            "Supply an explicit proposition, polarity and scope before comparing claims.")
    for pair in conflict["comparisons"]:
        target = ["claim:" + pair["left_claim_id"], "claim:" + pair["right_claim_id"]]
        if pair["unknown_scope_fields"]:
            add("comparison_scope_unknown", "scope", target,
                "Clarify the missing comparison dimensions.",
                fields=pair["unknown_scope_fields"])
        if pair["different_scope_fields"]:
            add("comparison_scope_different", "scope", target,
                "Examine whether the reported scope difference explains the disagreement.",
                fields=pair["different_scope_fields"])
        if not pair["claim_kinds_match"]:
            add("comparison_kind_different", "inference", target,
                "Distinguish the two types of claim before comparing their conclusions.")
        if pair["status"] == "potential_conflict_requires_review":
            add("potential_claim_conflict", "disagreement", target,
                "Inspect both propositions and source interpretations; do not select a winner automatically.")
        if pair["status"] == "polarity_unresolved":
            add("comparison_polarity_unknown", "disagreement", target,
                "Clarify whether each claim affirms or denies the proposition.")
        if pair["shared_source_opposite_stance_ids"]:
            add("shared_source_interpretation_differs", "disagreement", target,
                "Compare claim-specific readings of the shared sources.",
                source_ids=pair["shared_source_opposite_stance_ids"])
    totals = {}
    for entry in entries:
        category = entry["category"]
        totals[category] = totals.get(category, 0) + 1
    canonical = json.dumps(request.model_dump(), sort_keys=True, ensure_ascii=True,
                           separators=(",", ":")).encode("ascii")
    return {
        "schema_version": 1, "graph_sha256": checked["graph_sha256"],
        "conflict_review_sha256": conflict["conflict_review_sha256"],
        "uncertainty_review_sha256": hashlib.sha256(
            b"nexus-uncertainty-review-v1\x00" + canonical).hexdigest(),
        "status": "human_review_required",
        "unresolved_count": len(entries), "category_counts": totals,
        "entries": entries,
        "evidence": "structural_review_of_unverified_inputs",
        "probability_estimated": False, "completeness_guaranteed": False,
        "independent_verification": False, "execution_authorized": False,
    }


def register(app):
    @app.post("/studio/api/research/uncertainty-review")
    async def uncertainty_endpoint(request: Request):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=262144, timeout_seconds=10.0,
            too_large_detail="Uncertainty review too large",
            timeout_detail="Uncertainty review timed out", timeout_status=408,
        )
        try:
            result = inventory(UncertaintyRequest.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid uncertainty review", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)
