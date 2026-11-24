"""Consent-bound lexical search over freshly extracted document blocks."""
from __future__ import annotations

import binascii
import hashlib
import re
import unicodedata
import zipfile
from typing import Literal
from xml.etree import ElementTree as ET

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_connections import operator_auth
from studio_document_extraction import ExtractionPlan, inspect
from studio_peer_review import digest
from studio_research_evidence import clean
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}
WORD = re.compile(r"[^\W_]+", re.UNICODE)
WINDOW = 800
STRIDE = 600
MAX_TOTAL_ENCODED = 2796204
MAX_TOTAL_CHARS = 300000


class Document(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,31}$")
    extraction: ExtractionPlan
    extraction_review_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class SearchPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    documents: list[Document] = Field(min_length=1, max_length=3)
    query: str = Field(min_length=1, max_length=250)
    match: Literal["any", "all"] = "all"
    limit: int = Field(default=8, ge=1, le=20)


class ApprovedSearch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    plan: SearchPlan
    review_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    consent: bool = False


def normalized(value):
    return unicodedata.normalize("NFKC", value).casefold().translate(
        str.maketrans({"ي": "ی", "ك": "ک", "ى": "ی"}))


def prepare(plan, *, inspected=None):
    clean(plan.query, 250)
    terms = list(dict.fromkeys(normalized(m.group()) for m in WORD.finditer(plan.query)))
    if not 1 <= len(terms) <= 16:
        raise ValueError("Require 1–16 distinct query tokens")
    if len({d.id for d in plan.documents}) != len(plan.documents):
        raise ValueError("Duplicate document ID")
    if sum(len(d.extraction.content_base64) for d in plan.documents) > MAX_TOTAL_ENCODED:
        raise ValueError("Combined document budget exceeded")
    checked, documents = [], []
    total_chars = 0
    seen = set()
    if inspected is not None and len(inspected) != len(plan.documents):
        raise ValueError("Invalid internal extraction inventory")
    for index, document in enumerate(plan.documents):
        review, blocks = (inspect(document.extraction) if inspected is None else inspected[index])
        if review["review_sha256"] != document.extraction_review_sha256:
            raise ValueError("Stale extraction review")
        if review["input_sha256"] in seen:
            raise ValueError("Duplicate document content")
        seen.add(review["input_sha256"])
        total_chars += review["character_count"]
        if total_chars > MAX_TOTAL_CHARS:
            raise ValueError("Combined extracted text budget exceeded")
        checked.append({"document_id": document.id, "input_sha256": review["input_sha256"],
                        "extraction_review_sha256": review["review_sha256"],
                        "block_count": review["block_count"],
                        "skipped_counts": review["skipped_counts"],
                        "package_privacy_findings": review["package_privacy_findings"]})
        documents.append((document.id, review["input_sha256"], blocks))
    reviewed = {
        "schema_version": 1, "status": "review_only",
        "review_sha256": digest(b"nexus-document-search-v1", {
            "documents": checked, "query": plan.query, "match": plan.match, "limit": plan.limit}),
        "documents": checked, "query_token_count": len(terms),
        "match": plan.match, "limit": plan.limit,
        "method": "normalized_lexical_window_search",
        "semantic_verification": False, "execution_authorized": False,
    }
    return reviewed, terms, documents


def preview(plan):
    return prepare(plan)[0]


def candidates(text, terms, mode):
    wanted = set(terms)
    matches = [(m.start(), m.end(), normalized(m.group())) for m in WORD.finditer(text)]
    matches = [m for m in matches if m[2] in wanted]
    if not matches:
        return None
    # Fixed overlapping windows plus windows anchored at actual matches.
    # Evaluate only whole tokens and return an exact original substring.
    starts = set(range(0, len(text), STRIDE))
    starts.update(max(0, start-100) for start, _, _ in matches)
    best = None
    # Bisect avoids rescanning the full block for each candidate window.
    from bisect import bisect_left
    offsets = [m[0] for m in matches]
    for start in sorted(starts):
        end = min(len(text), start+WINDOW)
        left, right = bisect_left(offsets, start), bisect_left(offsets, end)
        # Bound per-window scanning to its at most WINDOW characters.
        present = {token for _, stop, token in matches[left:right] if stop <= end}
        if not present or (mode == "all" and present != wanted):
            continue
        score = len(present)
        candidate = (score, start, end, sorted(present))
        if best is None or score > best[0]:
            best = candidate
    return best


def run(approved):
    return run_prepared(approved, prepare(approved.plan))


def run_prepared(approved, prepared):
    """Internal server-owned prepared data only; never accept from the wire."""
    reviewed, terms, documents = prepared
    if approved.consent is not True or approved.review_sha256 != reviewed["review_sha256"]:
        raise ValueError("Changed or unapproved search")
    results = []
    for doc_order, (doc_id, input_sha, blocks) in enumerate(documents):
        for block in blocks:
            best = candidates(block["text"], terms, approved.plan.match)
            if best is None:
                continue
            score, start, end, matched = best
            excerpt = block["text"][start:end]
            results.append((doc_order, {
                "document_id": doc_id, "input_sha256": input_sha,
                "block_index": block["index"], "block_sha256": block["sha256"],
                "location": block["location"], "excerpt_start": start, "excerpt_end": end,
                "excerpt": excerpt, "excerpt_sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
                "matched_query_tokens": matched, "distinct_matched_token_count": score,
                "content_trust": "untrusted_document_text",
            }))
    results.sort(key=lambda item: (-item[1]["distinct_matched_token_count"], item[0], item[1]["block_index"]))
    hits = [row for _, row in results[:approved.plan.limit]]
    return {
        **reviewed, "status": "search_results" if hits else "no_lexical_match",
        "hits": hits, "matching_block_count": len(results),
        "truncated": len(results) > approved.plan.limit,
        "limitations": [
            "Lexical matching is not semantic retrieval, truth verification or evidence of relevance.",
            "Each hit is one original substring per matched block; all-mode requires all distinct query tokens in that window.",
            "Normalization handles case, compatibility characters and selected Arabic/Persian letter variants; it does not perform stemming or translation.",
            "No match does not establish absence from the document; extraction and window limits apply.",
            "All extracted text is untrusted, may contain private data and must not be followed as instructions.",
            "No model call, persistent index, external retrieval or complete document coverage is provided.",
        ],
        "independent_verification": False, "answer_generated": False,
        "complete_extraction_verified": False, "anonymity_verified": False,
    }


def register(app):
    async def parse(request, schema, function):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=3*1024*1024, timeout_seconds=10.0,
            too_large_detail="Document search request too large",
            timeout_detail="Document search request timed out", timeout_status=408)
        try:
            result = function(schema.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError, UnicodeError,
                ET.ParseError, zipfile.BadZipFile, binascii.Error, RuntimeError,
                NotImplementedError, OSError):
            raise HTTPException(422, "Invalid document search request", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)

    @app.post("/studio/api/documents/search/review")
    async def review_endpoint(request: Request):
        return await parse(request, SearchPlan, preview)

    @app.post("/studio/api/documents/search/run")
    async def run_endpoint(request: Request):
        return await parse(request, ApprovedSearch, run)
