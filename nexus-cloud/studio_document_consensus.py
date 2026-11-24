"""Compare server-issued document critique receipts without another provider call."""
from __future__ import annotations

import hmac
import os
from typing import Literal

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

import studio_model as model
from studio_connections import operator_auth
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}
Verdict = Literal["supported", "contradicted", "mixed", "insufficient"]
CONTEXT_DOMAIN = b"nexus-document-critique-context-v1"
RECEIPT_DOMAIN = b"nexus-document-critique-receipt-v1"


class Vote(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    statement_index: int = Field(ge=0, le=7)
    verdict: Verdict


class Receipt(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    model_slot: Literal["primary", "secondary", "tertiary"]
    configuration_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_review_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    context_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    critique_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    votes: list[Vote] = Field(min_length=1, max_length=8)
    signature: str = Field(pattern=r"^[a-f0-9]{64}$")


class Comparison(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    receipts: list[Receipt] = Field(min_length=2, max_length=3)


def issue(route, payload, review_id, out):
    # Compare the actual system/user context and requested token cap, not
    # provider wire syntax. Include system policy to reject policy drift.
    messages = ([{"role": "system", "content": payload["system"]}] + payload["messages"]
                if route.adapter == "anthropic" else payload["messages"])
    cap = payload.get("max_completion_tokens", payload.get("max_tokens"))
    context = model.comparison_tag(route.studio_token, CONTEXT_DOMAIN,
                                   [messages, cap, False])
    unsigned = {
        "model_slot": route.slot,
        "configuration_id": model.configuration_id(route),
        "request_review_id": review_id, "context_id": context,
        "critique_sha256": model.comparison_tag(route.studio_token,
                                               b"nexus-document-critique-result-v1", out),
        "votes": [{"statement_index": row["statement_index"],
                   "verdict": row["model_reported_verdict"]} for row in out["assessments"]],
    }
    return {**unsigned, "signature": model.comparison_tag(
        route.studio_token, RECEIPT_DOMAIN, unsigned)}


def compare(request, token):
    rows = request.receipts
    if len(token) < 32 or len({r.model_slot for r in rows}) != len(rows):
        raise ValueError("Invalid token or duplicate model slot")
    for row in rows:
        expected = model.comparison_tag(token, RECEIPT_DOMAIN, row.model_dump(exclude={"signature"}))
        if not hmac.compare_digest(row.signature, expected):
            raise ValueError("Invalid critique receipt")
        if [v.statement_index for v in row.votes] != list(range(len(row.votes))):
            raise ValueError("Invalid vote coverage")
    if len({r.context_id for r in rows}) != 1 or len({len(r.votes) for r in rows}) != 1:
        raise ValueError("Incompatible critique contexts")
    comparisons = []
    for i in range(len(rows[0].votes)):
        votes = [{"model_slot": row.model_slot, "verdict": row.votes[i].verdict}
                 for row in rows]
        distinct = {v["verdict"] for v in votes}
        unanimous = len(distinct) == 1
        comparisons.append({
            "statement_index": i, "votes": votes,
            "status": "unanimous_reported_verdict" if unanimous else "reported_disagreement",
            "unanimous_verdict": votes[0]["verdict"] if unanimous else None,
            "opposing_verdict_present": "contradicted" in distinct or "mixed" in distinct,
            "insufficient_verdict_present": "insufficient" in distinct,
            "human_review_required": True,
            "semantic_support_verified": False,
        })
    return {
        "schema_version": 1, "status": "human_review_required",
        "context_id": rows[0].context_id,
        "routes": [{"model_slot": r.model_slot, "configuration_id": r.configuration_id,
                    "critique_sha256": r.critique_sha256} for r in rows],
        "comparisons": comparisons,
        "disagreement_count": sum(c["status"] == "reported_disagreement" for c in comparisons),
        "limitations": [
            "Agreement compares reported categorical verdicts, not reasoning, truth or entailment.",
            "Different slots can share a provider, model, training data or biases.",
            "Receipts are replayable HMACs under a shared operator token; token holders can forge them.",
            "No majority vote, confidence probability, winner, independent reviewer or automatic correction is inferred.",
            "Only the reviewed excerpts and draft are in scope; omitted evidence may change the result.",
        ],
        "truth_verified": False, "semantic_agreement_verified": False,
        "independent_provenance_verified": False, "provider_contact_attempted": False,
        "automatic_correction_performed": False, "execution_authorized": False,
    }


def register(app):
    @app.post("/studio/api/documents/critique/comparison")
    async def endpoint(request: Request):
        operator_auth(request)
        token = os.getenv("NEXUS_STUDIO_TOKEN", "").strip()
        body = await read_bounded_body(
            request, max_bytes=16384, timeout_seconds=10.0,
            too_large_detail="Critique comparison too large",
            timeout_detail="Critique comparison timed out", timeout_status=408)
        try:
            out = compare(Comparison.model_validate_json(body), token)
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid or incompatible critique receipts",
                                headers=NO_STORE) from None
        return JSONResponse(out, headers=NO_STORE)
