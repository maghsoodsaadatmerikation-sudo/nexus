"""Deterministic review routing for a cited draft; no inference of truth."""
from __future__ import annotations

import binascii
import hmac
import os
import zipfile
from xml.etree import ElementTree as ET

import anyio
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

import studio_model as model
import studio_document_critique as critique
import studio_document_consensus as consensus
import studio_document_generation as generation
from studio_document_evidence import build
from studio_connections import operator_auth
from studio_peer_review import digest
from studio_research_evidence import clean
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    plan: critique.CritiquePlan
    receipts: list[consensus.Receipt] = Field(default_factory=list, max_length=3)


def review(request, token, catalog):
    context = request.plan.context
    clean(context.question, 1000)
    retrieved, rows, evidence_sha = build(context.evidence)
    if evidence_sha != context.evidence_sha256:
        raise ValueError("Stale evidence")
    ids = context.selected_evidence_ids
    by_id = {r["evidence_id"]: r for r in rows}
    if len(set(ids)) != len(ids) or any(key not in by_id for key in ids):
        raise ValueError("Unknown or duplicate selected evidence")
    selected = [by_id[key] for key in ids]
    status, statements = generation.validate_answer(request.plan.draft.model_dump_json(), selected)
    if status != "answer_with_checked_citations":
        raise ValueError("Nonempty cited draft required")

    # A receipt must belong to this exact draft, selected evidence, question,
    # token limit and current route configuration. No caller-asserted votes.
    receipts = request.receipts
    if len({r.model_slot for r in receipts}) != len(receipts):
        raise ValueError("Duplicate critique slot")
    for receipt in receipts:
        route = catalog.get(receipt.model_slot)
        if route is None or not hmac.compare_digest(route.studio_token, token):
            raise ValueError("Critique route unavailable")
        payload, _, _, rid = critique.prepare(request.plan, route)
        if (receipt.configuration_id != model.configuration_id(route)
                or not hmac.compare_digest(receipt.request_review_id, rid)):
            raise ValueError("Stale critique receipt")
        messages = ([{"role": "system", "content": payload["system"]}] + payload["messages"]
                    if route.adapter == "anthropic" else payload["messages"])
        cap = payload.get("max_completion_tokens", payload.get("max_tokens"))
        expected_context = model.comparison_tag(token, consensus.CONTEXT_DOMAIN,
                                                [messages, cap, False])
        expected = model.comparison_tag(token, consensus.RECEIPT_DOMAIN,
                                        receipt.model_dump(exclude={"signature"}))
        if (not hmac.compare_digest(receipt.signature, expected)
                or not hmac.compare_digest(receipt.context_id, expected_context)
                or [v.statement_index for v in receipt.votes] != list(range(len(statements)))):
            raise ValueError("Invalid critique receipt")
    if len(receipts) >= 2:
        consensus.compare(consensus.Comparison(receipts=receipts), token)

    actions = []

    def add(code, target, action):
        actions.append({"code": code, "target": target, "recommended_action": action,
                        "status": "unresolved"})

    add("source_truth_not_verified", None, "Inspect the original sources and their reliability.")
    add("lexical_retrieval_incomplete", None,
        "Consider alternative search terms and inspect relevant material not retrieved.")
    if retrieved["truncated"]:
        add("retrieval_limit_reached", None, "Review additional matching blocks.")
    if len(selected) < len(rows):
        add("some_retrieved_excerpts_not_selected", None,
            "Inspect omitted retrieved excerpts before expanding provider disclosure.")
    if any(doc["skipped_counts"] for doc in retrieved["documents"]):
        add("document_content_skipped", None, "Inspect unsupported or omitted document content locally.")
    if len(receipts) == 0:
        add("no_model_critique", None, "Consider a separately reviewed critique request or human review.")
    elif len(receipts) == 1:
        add("single_model_critique", None, "Consider an alternative reviewer if justified.")
    else:
        add("reviewer_independence_unverified", None, "Do not treat model agreement as independent evidence.")

    inventory = []
    for i, statement in enumerate(statements):
        votes = [{"model_slot": row.model_slot, "verdict": row.votes[i].verdict} for row in receipts]
        verdicts = {v["verdict"] for v in votes}
        if statement["kind"] == "interpretation":
            add("interpretation_unverified", i, "Check whether the cited passages actually entail the inference.")
        if len(verdicts) > 1:
            add("model_disagreement", i, "Compare the competing rationales and exact sources.")
        if verdicts & {"contradicted", "mixed"}:
            add("opposition_reported", i, "Inspect counterevidence and qualify or withhold the statement.")
        if "insufficient" in verdicts:
            add("insufficient_support_reported", i, "Seek additional relevant evidence or abstain.")
        if verdicts == {"supported"}:
            add("reported_support_not_truth", i, "Independently check relevance, context and support.")
        # Never elevate a quotation merely because multiple models agree.
        disposition = ("withhold_pending_review" if statement["kind"] == "interpretation"
                       or verdicts & {"contradicted", "mixed", "insufficient"}
                       else "exact_quote_candidate_requires_context_review")
        inventory.append({
            "statement_index": i, "kind": statement["kind"],
            "exact_quotation_verified": statement["exact_quotation_verified"],
            "reported_votes": votes, "disposition": disposition,
            "semantic_support_verified": False,
        })
    return {
        "schema_version": 1, "status": "human_review_required",
        "review_sha256": digest(b"nexus-document-metacognition-v1", request.model_dump()),
        "evidence_sha256": evidence_sha, "reviewer_count": len(receipts),
        "statement_inventory": inventory, "review_actions": actions,
        "action_count": len(actions),
        "limitations": [
            "This is a rule-based uncertainty inventory, not introspection or calibrated confidence.",
            "Receipts bind the current reviewed context under a shared operator token; token holders can forge them.",
            "An exact quote may still be misleading; model votes are not proof.",
            "No model call, external search, automatic correction, expanded disclosure or execution occurs.",
        ],
        "confidence_estimated": False, "truth_verified": False,
        "independent_verification": False, "provider_contact_attempted": False,
        "automatic_correction_performed": False, "execution_authorized": False,
    }


def register(app):
    @app.post("/studio/api/documents/metacognition")
    async def endpoint(request: Request):
        operator_auth(request)
        token = os.getenv("NEXUS_STUDIO_TOKEN", "").strip()
        body = await read_bounded_body(
            request, max_bytes=3*1024*1024, timeout_seconds=10.0,
            too_large_detail="Metacognitive review too large",
            timeout_detail="Metacognitive review timed out", timeout_status=408)
        try:
            data = ReviewRequest.model_validate_json(body)
            catalog = model.read_model_catalog() if data.receipts else {}
            result = await anyio.to_thread.run_sync(review, data, token, catalog)
        except (ValidationError, ValueError, RecursionError, UnicodeError,
                ET.ParseError, zipfile.BadZipFile, binascii.Error, RuntimeError,
                NotImplementedError, OSError):
            raise HTTPException(422, "Invalid metacognitive review", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)
