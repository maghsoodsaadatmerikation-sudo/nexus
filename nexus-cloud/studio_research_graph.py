"""Bounded knowledge graph of caller-supplied claims, concepts and evidence."""
from __future__ import annotations

import hashlib
import json
from typing import Annotated

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_connections import operator_auth
from studio_research_evidence import clean, review
from studio_research_reasoning import ReasoningRequest, assess
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}
NodeId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,31}$")]


class Concept(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: NodeId
    label: str = Field(min_length=1, max_length=120)


class ClaimNode(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: NodeId
    reasoning: ReasoningRequest
    concept_ids: list[NodeId] = Field(default_factory=list, max_length=12)


class GraphRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    claims: list[ClaimNode] = Field(min_length=1, max_length=6)
    concepts: list[Concept] = Field(default_factory=list, max_length=24)


def graph(request: GraphRequest):
    if sum(len(item.reasoning.evidence.cards) for item in request.claims) > 60:
        raise ValueError("Graph source-card budget exceeded")
    concept_ids = {concept.id for concept in request.concepts}
    if len(concept_ids) != len(request.concepts):
        raise ValueError("Duplicate concept ID")
    if len({claim.id for claim in request.claims}) != len(request.claims):
        raise ValueError("Duplicate claim ID")
    nodes = []
    edges = []
    sources = {}
    for concept in request.concepts:
        clean(concept.label, 120)
        nodes.append({"id": "concept:" + concept.id, "kind": "concept",
                      "label": concept.label, "status": "caller_supplied"})
    for claim in request.claims:
        if (len(set(claim.concept_ids)) != len(claim.concept_ids)
                or not set(claim.concept_ids) <= concept_ids):
            raise ValueError("Invalid concept references")
        checked = assess(claim.reasoning)
        inventory = review(claim.reasoning.evidence)
        claim_id = "claim:" + claim.id
        nodes.append({
            "id": claim_id, "kind": "claim", "claim_kind": checked["claim_kind"],
            "evidence_review_sha256": checked["evidence_review_sha256"],
            "reasoning_review_sha256": checked["reasoning_review_sha256"],
            "issues": checked["issues"], "status": "unverified",
        })
        for concept_id in claim.concept_ids:
            edges.append({"from": claim_id, "to": "concept:" + concept_id,
                          "relation": "caller_associated_concept"})
        for group in inventory["inventory"]:
            identity = group["identity"]
            # A source identity is shared across claims, but stance belongs to
            # the specific claim and never propagates to other claims.
            if identity not in sources:
                sources[identity] = {
                    "id": "source:" + hashlib.sha256(identity.encode("utf-8")).hexdigest(),
                    "kind": "source", "identity": identity,
                    "claim_ids": [], "status": "unverified_source_lead",
                }
            source = sources[identity]
            source["claim_ids"].append(claim_id)
            indices = group["source_indices"]
            edges.append({
                "from": source["id"], "to": claim_id,
                "relation": "caller_reported_" + group["caller_reported_stance"],
                "source_indices": indices,
                "source_kinds": group["kinds"],
                "providers": group["providers"],
                "metadata_only": group["metadata_only"],
                "method_annotations": [annotation for annotation in checked["annotations"]
                                       if annotation["source_index"] in indices],
                "evidence_review_sha256": inventory["review_sha256"],
            })
    nodes.extend(sources.values())
    canonical = json.dumps(request.model_dump(), sort_keys=True, ensure_ascii=True,
                           separators=(",", ":")).encode("ascii")
    return {
        "schema_version": 1,
        "graph_sha256": hashlib.sha256(b"nexus-knowledge-graph-v1\x00" + canonical).hexdigest(),
        "nodes": nodes, "edges": edges,
        "claim_count": len(request.claims),
        "concept_count": len(request.concepts),
        "distinct_source_identities": len(sources),
        "shared_source_ids": [source["id"] for source in sources.values()
                              if len(source["claim_ids"]) > 1],
        "evidence": "caller_supplied_relationships_and_reviewed_input_structure",
        "independent_verification": False,
        "semantic_inference": False,
        "execution_authorized": False,
    }


def register(app):
    @app.post("/studio/api/research/knowledge-graph")
    async def graph_endpoint(request: Request):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=262144, timeout_seconds=10.0,
            too_large_detail="Knowledge graph request too large",
            timeout_detail="Knowledge graph request timed out", timeout_status=408,
        )
        try:
            result = graph(GraphRequest.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid knowledge graph", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)
