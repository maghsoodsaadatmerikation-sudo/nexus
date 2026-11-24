"""Single reviewed document retrieval workflow built on the existing source contracts."""
from __future__ import annotations

import binascii
import zipfile
from typing import Literal
from xml.etree import ElementTree as ET

import anyio
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_connections import operator_auth
from studio_document_extraction import ExtractionPlan, inspect
import studio_document_search as search
import studio_document_evidence as evidence
from studio_peer_review import digest
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}


class InputDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,31}$")
    extraction: ExtractionPlan


class DocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    documents: list[InputDocument] = Field(min_length=1, max_length=3)
    query: str = Field(min_length=1, max_length=250)
    match: Literal["any", "all"] = "all"
    limit: int = Field(default=8, ge=1, le=20)


class ApprovedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    plan: DocumentRequest
    review_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    consent: bool = False


def prepare(plan):
    if len({d.id for d in plan.documents}) != len(plan.documents):
        raise ValueError("Duplicate document ID")
    if sum(len(d.extraction.content_base64) for d in plan.documents) > search.MAX_TOTAL_ENCODED:
        raise ValueError("Combined document budget exceeded")
    inspected, documents = [], []
    for d in plan.documents:
        checked, blocks = inspect(d.extraction)
        inspected.append((checked, blocks))
        documents.append(search.Document(id=d.id, extraction=d.extraction,
                                         extraction_review_sha256=checked["review_sha256"]))
    search_plan = search.SearchPlan(documents=documents, query=plan.query,
                                    match=plan.match, limit=plan.limit)
    # Reuse freshly inspected blocks only within this server call, never from
    # caller-supplied evidence. The same validation and hash path is preserved.
    prepared = search.prepare(search_plan, inspected=inspected)
    checked = prepared[0]
    binding = {"search_review_sha256": checked["review_sha256"],
               "document_ids": [d.id for d in documents],
               "disclosure": "studio_excerpts_only_no_provider"}
    reviewed = {
        "schema_version": 1, "status": "review_only",
        "review_sha256": digest(b"nexus-integrated-document-review-v1", binding),
        "search_review_sha256": checked["review_sha256"],
        "documents": checked["documents"], "query_token_count": checked["query_token_count"],
        "match": plan.match, "limit": plan.limit,
        "provider_contact_attempted": False, "provider_disclosure_authorized": False,
        "execution_authorized": False,
        "limitations": [
            "Review processes original file bytes at the Studio gateway; this is not device-only.",
            "Review returns no source excerpts. Run requires explicit consent and unchanged inputs.",
            "Only bounded TXT and DOCX lexical retrieval is supported.",
            "No external model or network source is contacted by this workflow.",
        ],
    }
    return reviewed, search_plan, prepared


def preview(plan):
    return prepare(plan)[0]


def run(approved):
    reviewed, search_plan, prepared = prepare(approved.plan)
    if approved.consent is not True or approved.review_sha256 != reviewed["review_sha256"]:
        raise ValueError("Changed or unapproved document workflow")
    approved_search = search.ApprovedSearch(plan=search_plan,
                                           review_sha256=reviewed["search_review_sha256"],
                                           consent=True)
    retrieved = search.run_prepared(approved_search, prepared)
    bundle = evidence.render_evidence(retrieved, include_excerpts=True)
    # Expose enough descriptors to reconstruct the existing EvidenceRequest
    # using the caller's original files; never echo base64 or assert consent
    # to a downstream model call.
    return {
        "schema_version": 1, "status": bundle["status"],
        "review_sha256": reviewed["review_sha256"],
        "evidence": bundle,
        "handoff": {
            "search_review_sha256": reviewed["search_review_sha256"],
            "documents": reviewed["documents"],
            "query": approved.plan.query, "match": approved.plan.match, "limit": approved.plan.limit,
            "generation_review_endpoint": "/studio/api/documents/generation/review",
            "requires_original_files": True, "requires_separate_provider_consent": True,
        },
        "provider_contact_attempted": False, "provider_disclosure_authorized": False,
        "semantic_verification": False, "execution_authorized": False,
    }


def register(app):
    async def parse(request, schema, fn):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=3*1024*1024, timeout_seconds=10.0,
            too_large_detail="Document workflow too large",
            timeout_detail="Document workflow timed out", timeout_status=408)
        try:
            data = schema.model_validate_json(body)
            result = await anyio.to_thread.run_sync(fn, data)
        except (ValidationError, ValueError, RecursionError, UnicodeError,
                ET.ParseError, zipfile.BadZipFile, binascii.Error, RuntimeError,
                NotImplementedError, OSError):
            raise HTTPException(422, "Invalid or stale document workflow", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)

    @app.post("/studio/api/documents/workflow/review")
    async def review_endpoint(request: Request):
        return await parse(request, DocumentRequest, preview)

    @app.post("/studio/api/documents/workflow/run")
    async def run_endpoint(request: Request):
        return await parse(request, ApprovedRequest, run)
