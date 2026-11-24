"""Conservative scientific claim review over explicitly supplied evidence annotations."""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_connections import operator_auth
from studio_research_evidence import EvidenceRequest, review
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}


class MethodAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source_index: int = Field(ge=0, le=59)
    design: Literal["unknown", "background", "case_report", "cross_sectional",
                    "cohort", "case_control", "randomized_trial", "systematic_review",
                    "quasi_experimental", "mechanistic"]
    excerpt_start: int = Field(ge=0, le=2399)
    excerpt_end: int = Field(ge=1, le=2400)
    population_match: Literal["reported_match", "reported_mismatch", "unknown"] = "unknown"
    limitations_reviewed: bool = False


class ReasoningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    evidence: EvidenceRequest
    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    claim_kind: Literal["hypothesis", "observation", "association", "causal", "prediction"]
    annotations: list[MethodAnnotation] = Field(default_factory=list, max_length=60)


def assess(request: ReasoningRequest):
    inventory = review(request.evidence)
    if request.review_sha256 != inventory["review_sha256"]:
        raise ValueError("Stale evidence review")
    annotations = {}
    assessments = {item.source_index: item.stance for item in request.evidence.assessments}
    for item in request.annotations:
        i = item.source_index
        if i in annotations or i >= len(request.evidence.cards):
            raise ValueError("Invalid or duplicate annotation")
        card = request.evidence.cards[i]
        if card.kind == "bibliographic-metadata-only":
            raise ValueError("Metadata cannot establish study design")
        if not item.excerpt_start < item.excerpt_end <= len(card.excerpt):
            raise ValueError("Invalid excerpt span")
        excerpt = card.excerpt[item.excerpt_start:item.excerpt_end]
        if not excerpt.strip():
            raise ValueError("Empty excerpt span")
        if card.kind == "encyclopedia-excerpt" and item.design not in ("unknown", "background"):
            raise ValueError("Encyclopedia excerpt cannot be classified as primary study")
        annotations[i] = {
            **item.model_dump(),
            "excerpt_sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
            "stance": assessments.get(i, "unclear"),
            "evidence": "caller_reported_annotation_not_verified",
        }
    issues = []
    if inventory["reported_disagreement"]:
        issues.append("reported_disagreement_requires_reconciliation")
    if not inventory["stance_counts"]["supports"]:
        issues.append("no_unambiguously_supporting_source_identity_reported")
    if any(group["metadata_only"] for group in inventory["inventory"]):
        issues.append("metadata_only_sources_not_substantive_evidence")
    supporting = [i for i, stance in assessments.items() if stance == "supports"]
    if any(i not in annotations for i in supporting):
        issues.append("supporting_source_design_unannotated")
    annotated_support = [annotations[i] for i in supporting if i in annotations]
    if not annotated_support or any(a["design"] in ("unknown", "background") for a in annotated_support):
        issues.append("study_design_uncertain")
    if not annotated_support or any(a["population_match"] != "reported_match" for a in annotated_support):
        issues.append("applicability_unresolved")
    if not annotated_support or any(not a["limitations_reviewed"] for a in annotated_support):
        issues.append("limitations_review_incomplete")
    if request.claim_kind == "causal":
        if not any(a["design"] in ("randomized_trial", "quasi_experimental")
                   for a in annotated_support):
            issues.append("no_supporting_causal_design_reported")
        issues.append("causal_identification_not_verified")
    elif request.claim_kind == "prediction":
        issues.append("out_of_sample_validation_not_verified")
    elif request.claim_kind == "association":
        issues.append("association_does_not_establish_causation")
    elif request.claim_kind == "hypothesis":
        issues.append("hypothesis_not_established_finding")
    else:
        issues.append("observation_not_generalizable_without_review")
    canonical = json.dumps(request.model_dump(), sort_keys=True, ensure_ascii=True,
                           separators=(",", ":")).encode("ascii")
    return {
        "schema_version": 1,
        "evidence_review_sha256": inventory["review_sha256"],
        "reasoning_review_sha256": hashlib.sha256(
            b"nexus-reasoning-review-v1\x00" + canonical).hexdigest(),
        "claim_kind": request.claim_kind,
        "status": "human_review_required",
        "issues": issues,
        "annotations": [annotations[i] for i in sorted(annotations)],
        "stance_counts": inventory["stance_counts"],
        "claim_verified": False,
        "causality_established": False,
        "independent_verification": False,
        "execution_authorized": False,
    }


def register(app):
    @app.post("/studio/api/research/reasoning-review")
    async def reasoning_endpoint(request: Request):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=262144, timeout_seconds=10.0,
            too_large_detail="Reasoning request too large",
            timeout_detail="Reasoning request timed out", timeout_status=408,
        )
        try:
            result = assess(ReasoningRequest.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid reasoning review", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)
