"""Review a structured research draft against its exact upstream evidence."""
from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_connections import operator_auth
from studio_research_graph import NodeId, graph
from studio_research_perspectives import PerspectiveRequest, compare_perspectives
from studio_research_uncertainty import inventory
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}
SourceId = Annotated[str, Field(pattern=r"^source:[0-9a-f]{64}$")]
IssueId = Annotated[str, Field(pattern=r"^u-[0-9a-f]{64}$")]
ClaimId = Annotated[str, Field(pattern=r"^claim:[a-z][a-z0-9_-]{0,31}$")]


class SourceLink(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source_id: SourceId
    relation: Literal["caller_reported_supports", "caller_reported_challenges",
                      "caller_reported_mixed", "caller_reported_unassessed_or_unclear"]
    metadata_only: bool


class ClaimDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    claim_id: ClaimId
    status: Literal["unverified", "verified", "causality_established"]
    sources: list[SourceLink] = Field(max_length=60)


class ViewDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    perspective_id: NodeId
    claim_ids: list[ClaimId] = Field(max_length=6)


class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    claims: list[ClaimDraft] = Field(max_length=6)
    perspectives: list[ViewDraft] = Field(max_length=6)
    unresolved_item_ids: list[IssueId] = Field(max_length=400)
    independent_verification: bool
    execution_authorized: bool


class CritiqueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    perspective_request: PerspectiveRequest
    perspective_review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate: Draft | None = None


def expected_draft(request):
    checked = compare_perspectives(request.perspective_request)
    if checked["perspective_review_sha256"] != request.perspective_review_sha256:
        raise ValueError("Stale perspective review")
    upstream = request.perspective_request.uncertainty_request
    evidence_graph = graph(upstream.conflict_request.graph_request)
    uncertainty = inventory(upstream)
    claims = []
    for node in evidence_graph["nodes"]:
        if node["kind"] != "claim":
            continue
        links = [{"source_id": edge["from"], "relation": edge["relation"],
                  "metadata_only": edge["metadata_only"]}
                 for edge in evidence_graph["edges"]
                 if edge["to"] == node["id"] and edge["from"].startswith("source:")]
        claims.append({"claim_id": node["id"], "status": "unverified", "sources": links})
    return Draft.model_validate({
        "claims": claims,
        "perspectives": [{"perspective_id": view["id"], "claim_ids": view["claim_ids"]}
                         for view in checked["perspectives"]],
        "unresolved_item_ids": [entry["id"] for entry in uncertainty["entries"]],
        "independent_verification": False, "execution_authorized": False,
    })


def critique(request: CritiqueRequest):
    expected = expected_draft(request)
    findings = []

    def compare_keys(actual, required, code, target):
        if len(actual) != len(set(actual)):
            findings.append({"code": "duplicate_" + code, "target": target})
        missing = sorted(set(required) - set(actual))
        extra = set(actual) - set(required)
        if missing:
            findings.append({"code": "missing_" + code, "target": target, "expected_ids": missing})
        if extra:
            findings.append({"code": "unexpected_" + code, "target": target, "count": len(extra)})

    candidate = request.candidate
    if candidate is not None:
        expected_claims = {row.claim_id: row for row in expected.claims}
        compare_keys([row.claim_id for row in candidate.claims],
                     expected_claims.keys(), "claim", "draft")
        for row in candidate.claims:
            if row.claim_id not in expected_claims:
                continue
            required = expected_claims[row.claim_id]
            if row.status != required.status:
                findings.append({"code": "unsupported_verification_status", "target": row.claim_id})
            links = {link.source_id: link for link in required.sources}
            compare_keys([link.source_id for link in row.sources],
                         links.keys(), "source_link", row.claim_id)
            for link in row.sources:
                if link.source_id in links and link != links[link.source_id]:
                    findings.append({"code": "altered_source_relation_or_kind",
                                     "target": row.claim_id, "source_id": link.source_id})
        expected_views = {row.perspective_id: row for row in expected.perspectives}
        compare_keys([row.perspective_id for row in candidate.perspectives],
                     expected_views.keys(), "perspective", "draft")
        for row in candidate.perspectives:
            if row.perspective_id in expected_views:
                compare_keys(row.claim_ids, expected_views[row.perspective_id].claim_ids,
                             "perspective_membership", row.perspective_id)
        compare_keys(candidate.unresolved_item_ids, expected.unresolved_item_ids,
                     "uncertainty_item", "draft")
        if candidate.independent_verification or candidate.execution_authorized:
            findings.append({"code": "unsupported_authority_or_verification", "target": "draft"})
    canonical = json.dumps(expected.model_dump(), sort_keys=True, ensure_ascii=True,
                           separators=(",", ":")).encode("ascii")
    return {
        "schema_version": 1,
        "perspective_review_sha256": request.perspective_review_sha256,
        "reference_draft_sha256": hashlib.sha256(
            b"nexus-research-draft-v1\x00" + request.perspective_review_sha256.encode("ascii")
            + b"\x00" + canonical).hexdigest(),
        "status": ("reference_draft" if candidate is None else
                   "revision_required" if findings else "structurally_consistent"),
        "finding_count": len(findings),
        "findings": findings[:100],
        "findings_truncated": len(findings) > 100,
        "reference_draft": expected.model_dump(),
        "evidence": "structural_comparison_against_unverified_inputs",
        "human_review_required": True,
        "semantic_verification": False,
        "independent_verification": False,
        "execution_authorized": False,
    }


def register(app):
    @app.post("/studio/api/research/draft-critique")
    async def critique_endpoint(request: Request):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=393216, timeout_seconds=10.0,
            too_large_detail="Research critique too large",
            timeout_detail="Research critique timed out", timeout_status=408,
        )
        try:
            payload = CritiqueRequest.model_validate_json(body)
            # Preserve the upstream transport budget for nested research data.
            if len(payload.perspective_request.model_dump_json().encode("utf-8")) > 262144:
                raise ValueError("Research input budget exceeded")
            result = critique(payload)
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid research critique", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)
