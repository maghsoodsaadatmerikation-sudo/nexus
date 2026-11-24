"""Evidence-bound multi-claim synthesis report, without invented conclusions."""
from __future__ import annotations

import hashlib
import json

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_connections import operator_auth
from studio_research_citations import canonical_url
from studio_research_conflicts import compare_claims
from studio_research_critique import CritiqueRequest, critique
from studio_research_graph import graph
from studio_research_perspectives import compare_perspectives
from studio_research_uncertainty import inventory
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}


class SynthesisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    review: CritiqueRequest
    reference_draft_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    include_claim_text: bool = False


def synthesize(request: SynthesisRequest):
    if len(request.review.perspective_request.model_dump_json().encode("utf-8")) > 262144:
        raise ValueError("Research input budget exceeded")
    checked = critique(request.review)
    if checked["reference_draft_sha256"] != request.reference_draft_sha256:
        raise ValueError("Stale reference draft")
    if checked["status"] not in ("reference_draft", "structurally_consistent"):
        raise ValueError("Draft requires revision")
    perspective_request = request.review.perspective_request
    uncertainty_request = perspective_request.uncertainty_request
    conflict_request = uncertainty_request.conflict_request
    graph_request = conflict_request.graph_request
    reviewed_graph = graph(graph_request)
    uncertainties = inventory(uncertainty_request)
    conflicts = compare_claims(conflict_request)
    perspectives = compare_perspectives(perspective_request)
    claim_input = {"claim:" + claim.id: claim.reasoning.evidence for claim in graph_request.claims}
    references = []
    by_id = {}
    for node in reviewed_graph["nodes"]:
        if node["kind"] != "source":
            continue
        titles = []
        for edge in reviewed_graph["edges"]:
            if edge["from"] != node["id"]:
                continue
            cards = claim_input[edge["to"]].cards
            for index in edge["source_indices"]:
                title = " ".join(cards[index].title.split())
                if title not in titles:
                    titles.append(title)
        conflict = len({title.casefold() for title in titles}) > 1
        number = len(references) + 1
        entry = {
            "number": number, "source_id": node["id"], "identity": node["identity"],
            "url": canonical_url(node["identity"]),
            "title": None if conflict else titles[0],
            "title_conflict": conflict,
            "conflicting_titles": titles if conflict else [],
            "missing_metadata": ["author", "issued"] + (
                [] if node["identity"].startswith("wiki:") else ["container-title"]
            ) + (["title"] if conflict else []),
            "status": "incomplete_unverified",
        }
        references.append(entry)
        by_id[node["id"]] = number

    claims = []
    for node in reviewed_graph["nodes"]:
        if node["kind"] != "claim":
            continue
        key = node["id"]
        links = [
            {"reference_number": by_id[edge["from"]],
             "source_id": edge["from"], "relation": edge["relation"],
             "metadata_only": edge["metadata_only"], "source_indices": edge["source_indices"],
             "method_annotations": edge["method_annotations"],
             "evidence_review_sha256": edge["evidence_review_sha256"]}
            for edge in reviewed_graph["edges"]
            if edge["to"] == key and edge["from"].startswith("source:")
        ]
        row = {
            "claim_id": key, "claim_kind": node["claim_kind"], "status": "unverified",
            "reference_links": links,
            "reasoning_review_sha256": node["reasoning_review_sha256"],
            "uncertainty_ids": [item["id"] for item in uncertainties["entries"]
                                if key in item["target"]],
        }
        if request.include_claim_text:
            row["caller_supplied_claim"] = claim_input[key].claim
        claims.append(row)
    report = {
        "schema_version": 1,
        "status": "research_synthesis_draft",
        "reference_draft_sha256": checked["reference_draft_sha256"],
        "graph_sha256": reviewed_graph["graph_sha256"],
        "claims": claims, "references": references,
        "perspectives": [{"id": view["id"], "label": view["label"],
                          "claim_ids": view["claim_ids"],
                          "unresolved_item_ids": view["unresolved_item_ids"]}
                         for view in perspectives["perspectives"]],
        "unassigned_claim_ids": perspectives["unassigned_claim_ids"],
        "claim_comparisons": conflicts["comparisons"],
        "unframed_claim_ids": conflicts["unframed_claim_ids"],
        "uncertainties": uncertainties["entries"],
        "limitations": [
            "Sources and interpretations are caller supplied and not independently verified.",
            "Shared source identity does not imply independent evidence.",
            "Reference metadata is incomplete; no bibliographic fields were invented.",
            "No substantive conclusion, causal inference, consensus or evidence weight is inferred.",
        ],
        "claim_text_included": request.include_claim_text,
        "human_review_required": True,
        "semantic_verification": False, "independent_verification": False,
        "execution_authorized": False,
    }
    canonical = json.dumps(report, sort_keys=True, ensure_ascii=True,
                           separators=(",", ":")).encode("ascii")
    return {**report, "report_sha256": hashlib.sha256(
        b"nexus-research-synthesis-v1\x00" + canonical).hexdigest()}


def register(app):
    @app.post("/studio/api/research/synthesis")
    async def synthesis_endpoint(request: Request):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=393216, timeout_seconds=10.0,
            too_large_detail="Research synthesis too large",
            timeout_detail="Research synthesis timed out", timeout_status=408,
        )
        try:
            result = synthesize(SynthesisRequest.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid research synthesis", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)
