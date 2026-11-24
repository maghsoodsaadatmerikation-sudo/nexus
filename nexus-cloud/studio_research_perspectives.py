"""Compare explicitly supplied perspectives without ranking or propagating evidence."""
from __future__ import annotations

import hashlib
import json
from itertools import combinations

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_connections import operator_auth
from studio_research_evidence import clean
from studio_research_graph import NodeId, graph
from studio_research_conflicts import compare_claims
from studio_research_uncertainty import UncertaintyRequest, inventory
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}


class Perspective(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: NodeId
    label: str = Field(min_length=1, max_length=120)
    claim_ids: list[NodeId] = Field(min_length=1, max_length=6)


class PerspectiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    uncertainty_request: UncertaintyRequest
    uncertainty_review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    perspectives: list[Perspective] = Field(min_length=2, max_length=6)


def compare_perspectives(request: PerspectiveRequest):
    uncertainty = inventory(request.uncertainty_request)
    if uncertainty["uncertainty_review_sha256"] != request.uncertainty_review_sha256:
        raise ValueError("Stale uncertainty review")
    conflict_request = request.uncertainty_request.conflict_request
    checked = graph(conflict_request.graph_request)
    conflicts = compare_claims(conflict_request)
    claims = {node["id"]: node for node in checked["nodes"] if node["kind"] == "claim"}
    if len({item.id for item in request.perspectives}) != len(request.perspectives):
        raise ValueError("Duplicate perspective ID")
    assigned = set()
    views = []
    for item in request.perspectives:
        clean(item.label, 120)
        ids = {"claim:" + key for key in item.claim_ids}
        if len(ids) != len(item.claim_ids) or not ids <= claims.keys():
            raise ValueError("Invalid perspective claim references")
        assigned.update(ids)
        source_edges = [
            edge for edge in checked["edges"]
            if edge["from"].startswith("source:") and edge["to"] in ids
        ]
        source_ids = sorted({edge["from"] for edge in source_edges})
        applicable = [entry["id"] for entry in uncertainty["entries"]
                      if ids.intersection(entry["target"])]
        views.append({
            "id": item.id, "label": item.label,
            "claim_ids": sorted(ids),
            "source_ids": source_ids,
            "claim_source_links": source_edges,
            "unresolved_item_ids": applicable,
            "status": "caller_defined_unverified_perspective",
        })
    comparisons = []
    for left, right in combinations(views, 2):
        left_claims, right_claims = set(left["claim_ids"]), set(right["claim_ids"])
        left_sources, right_sources = set(left["source_ids"]), set(right["source_ids"])
        # A common claim is not counted as an inter-perspective disagreement.
        left_only, right_only = left_claims - right_claims, right_claims - left_claims
        pairs = []
        for pair in conflicts["comparisons"]:
            a, b = "claim:" + pair["left_claim_id"], "claim:" + pair["right_claim_id"]
            if (a in left_only and b in right_only) or (b in left_only and a in right_only):
                pairs.append(pair)
        comparisons.append({
            "left_perspective_id": left["id"], "right_perspective_id": right["id"],
            "shared_claim_ids": sorted(left_claims & right_claims),
            "left_only_claim_ids": sorted(left_only),
            "right_only_claim_ids": sorted(right_only),
            "shared_source_ids": sorted(left_sources & right_sources),
            "left_only_source_ids": sorted(left_sources - right_sources),
            "right_only_source_ids": sorted(right_sources - left_sources),
            "cross_view_claim_comparisons": pairs,
            "potential_conflict_count": sum(
                pair["status"] == "potential_conflict_requires_review" for pair in pairs),
        })
    canonical = json.dumps(request.model_dump(), sort_keys=True, ensure_ascii=True,
                           separators=(",", ":")).encode("ascii")
    return {
        "schema_version": 1,
        "uncertainty_review_sha256": uncertainty["uncertainty_review_sha256"],
        "perspective_review_sha256": hashlib.sha256(
            b"nexus-perspective-review-v1\x00" + canonical).hexdigest(),
        "perspectives": views,
        "comparisons": comparisons,
        "unassigned_claim_ids": sorted(claims.keys() - assigned),
        "status": "human_review_required",
        "evidence": "caller_defined_views_of_unverified_claims",
        "perspective_ranking_performed": False,
        "semantic_inference": False,
        "independent_verification": False,
        "execution_authorized": False,
    }


def register(app):
    @app.post("/studio/api/research/perspective-review")
    async def perspective_endpoint(request: Request):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=262144, timeout_seconds=10.0,
            too_large_detail="Perspective review too large",
            timeout_detail="Perspective review timed out", timeout_status=408,
        )
        try:
            result = compare_perspectives(PerspectiveRequest.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid perspective review", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)
