"""Review potential claim conflicts using explicit caller-normalized propositions."""
from __future__ import annotations

import hashlib
import json
from itertools import combinations
from typing import Literal

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_connections import operator_auth
from studio_research_graph import GraphRequest, NodeId, graph
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}
DIMENSIONS = ("population", "setting", "period", "measurement", "conditions")


class Scope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    population: NodeId | None = None
    setting: NodeId | None = None
    period: NodeId | None = None
    measurement: NodeId | None = None
    conditions: NodeId | None = None


class PropositionFrame(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    claim_id: NodeId
    proposition_id: NodeId
    polarity: Literal["affirms", "denies", "uncertain"]
    scope: Scope


class ConflictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    graph_request: GraphRequest
    graph_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    frames: list[PropositionFrame] = Field(min_length=1, max_length=6)


def compare_claims(request: ConflictRequest):
    checked = graph(request.graph_request)
    if checked["graph_sha256"] != request.graph_sha256:
        raise ValueError("Stale graph review")
    claims = {claim.id: claim for claim in request.graph_request.claims}
    frames = {frame.claim_id: frame for frame in request.frames}
    if len(frames) != len(request.frames) or not frames.keys() <= claims.keys():
        raise ValueError("Invalid or duplicate claim frame")
    source_edges = {claim_id: {} for claim_id in claims}
    for edge in checked["edges"]:
        if edge["from"].startswith("source:"):
            source_edges[edge["to"][6:]][edge["from"]] = edge["relation"]
    comparisons = []
    for left_id, right_id in combinations(claims, 2):
        if left_id not in frames or right_id not in frames:
            continue
        left, right = frames[left_id], frames[right_id]
        if left.proposition_id != right.proposition_id:
            continue
        different = [key for key in DIMENSIONS
                     if getattr(left.scope, key) is not None
                     and getattr(right.scope, key) is not None
                     and getattr(left.scope, key) != getattr(right.scope, key)]
        unknown = [key for key in DIMENSIONS
                   if getattr(left.scope, key) is None or getattr(right.scope, key) is None]
        kinds_match = claims[left_id].reasoning.claim_kind == claims[right_id].reasoning.claim_kind
        opposite = {left.polarity, right.polarity} == {"affirms", "denies"}
        if different:
            status = "different_reported_scope"
        elif unknown:
            status = "scope_unresolved"
        elif not kinds_match:
            status = "different_claim_kind"
        elif opposite:
            status = "potential_conflict_requires_review"
        elif "uncertain" in (left.polarity, right.polarity):
            status = "polarity_unresolved"
        else:
            status = "same_reported_polarity"
        shared = source_edges[left_id].keys() & source_edges[right_id].keys()
        opposite_labels = sorted(source for source in shared
                                 if {source_edges[left_id][source], source_edges[right_id][source]}
                                 == {"caller_reported_supports", "caller_reported_challenges"})
        comparisons.append({
            "left_claim_id": left_id, "right_claim_id": right_id,
            "proposition_id": left.proposition_id, "status": status,
            "different_scope_fields": different, "unknown_scope_fields": unknown,
            "claim_kinds_match": kinds_match, "opposite_reported_polarity": opposite,
            "shared_source_ids": sorted(shared),
            "shared_source_opposite_stance_ids": opposite_labels,
            "contradiction_verified": False,
        })
    canonical = json.dumps(request.model_dump(), sort_keys=True, ensure_ascii=True,
                           separators=(",", ":")).encode("ascii")
    return {
        "schema_version": 1, "graph_sha256": checked["graph_sha256"],
        "conflict_review_sha256": hashlib.sha256(
            b"nexus-conflict-review-v1\x00" + canonical).hexdigest(),
        "comparisons": comparisons,
        "unframed_claim_ids": [key for key in claims if key not in frames],
        "potential_conflict_count": sum(item["status"] == "potential_conflict_requires_review"
                                        for item in comparisons),
        "status": "human_review_required",
        "evidence": "caller_normalized_proposition_and_scope_only",
        "semantic_inference": False, "independent_verification": False,
        "execution_authorized": False,
    }


def register(app):
    @app.post("/studio/api/research/conflict-review")
    async def conflict_endpoint(request: Request):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=262144, timeout_seconds=10.0,
            too_large_detail="Conflict review too large",
            timeout_detail="Conflict review timed out", timeout_status=408,
        )
        try:
            result = compare_claims(ConflictRequest.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid conflict review", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)
