"""Review caller-authored academic manuscripts against a research synthesis."""
from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_connections import operator_auth
from studio_research_critique import ClaimId
from studio_research_synthesis import SynthesisRequest, synthesize
from studio_research_evidence import clean
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}
SectionId = Literal["abstract", "introduction", "methods", "results", "discussion",
                    "limitations", "conclusion", "declarations"]
RefNumber = Annotated[int, Field(ge=1, le=60)]
REQUIRED = {
    "empirical": ("abstract", "introduction", "methods", "results", "discussion",
                  "limitations", "declarations"),
    "conceptual": ("abstract", "introduction", "discussion", "limitations", "conclusion",
                   "declarations"),
    "commentary": ("introduction", "discussion", "limitations", "declarations"),
}


class ClaimCitation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    claim_id: ClaimId
    references: list[RefNumber] = Field(max_length=60)


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: SectionId
    text: str = Field(min_length=1, max_length=12000)
    citations: list[ClaimCitation] = Field(default_factory=list, max_length=6)


class Limits(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    title_words: int = Field(default=40, ge=1, le=200)
    abstract_words: int = Field(default=250, ge=1, le=2000)
    manuscript_words: int = Field(default=6000, ge=1, le=20000)


class ManuscriptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    synthesis: SynthesisRequest
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    article_type: Literal["empirical", "conceptual", "commentary"]
    title: str = Field(min_length=1, max_length=500)
    sections: list[Section] = Field(min_length=1, max_length=8)
    limits: Limits = Field(default_factory=Limits)


def words(value: str) -> int:
    return len(value.split())


def review(request: ManuscriptRequest):
    report = synthesize(request.synthesis)
    if request.report_sha256 != report["report_sha256"]:
        raise ValueError("Stale synthesis report")
    clean(request.title, 500)
    present = {section.id for section in request.sections}
    if len(present) != len(request.sections):
        raise ValueError("Duplicate section")
    claims = {row["claim_id"]: row for row in report["claims"]}
    findings = []
    linked = set()
    counts = {}
    for section in request.sections:
        clean(section.text, 12000)
        counts[section.id] = words(section.text)
        if len({link.claim_id for link in section.citations}) != len(section.citations):
            raise ValueError("Duplicate section claim")
        for link in section.citations:
            if link.claim_id not in claims or len(set(link.references)) != len(link.references):
                raise ValueError("Invalid claim or duplicate reference")
            row = claims[link.claim_id]
            source_links = {item["reference_number"]: item for item in row["reference_links"]}
            if not set(link.references) <= source_links.keys():
                raise ValueError("Reference not associated with claim")
            linked.add(link.claim_id)
            target = {"section": section.id, "claim_id": link.claim_id}
            if not link.references:
                findings.append({**target, "code": "claim_without_reference"})
            if link.references and all(source_links[n]["metadata_only"] for n in link.references):
                findings.append({**target, "code": "metadata_only_citations"})
            omitted = sorted(n for n, item in source_links.items()
                             if item["relation"] in ("caller_reported_challenges", "caller_reported_mixed")
                             and n not in link.references)
            if omitted:
                findings.append({**target, "code": "opposing_source_not_linked",
                                 "reference_numbers": omitted})
    for section_id in REQUIRED[request.article_type]:
        if section_id not in present:
            findings.append({"code": "missing_section", "section": section_id})
    for claim_id in sorted(claims.keys() - linked):
        findings.append({"code": "unmapped_reviewed_claim", "claim_id": claim_id})
    title_count = words(request.title)
    abstract_count = counts.get("abstract", 0)
    body_count = sum(counts.values())
    for field, actual, maximum in (
        ("title", title_count, request.limits.title_words),
        ("abstract", abstract_count, request.limits.abstract_words),
        ("manuscript", body_count, request.limits.manuscript_words),
    ):
        if actual > maximum:
            findings.append({"code": "word_limit_exceeded", "field": field,
                             "actual": actual, "limit": maximum})
    canonical = json.dumps(request.model_dump(), ensure_ascii=True, sort_keys=True,
                           separators=(",", ":")).encode("ascii")
    return {
        "schema_version": 1,
        "manuscript_review_sha256": hashlib.sha256(
            b"nexus-academic-review-v1\x00" + canonical).hexdigest(),
        "report_sha256": report["report_sha256"],
        "article_type": request.article_type,
        "status": "revision_required" if findings else "structural_checks_passed",
        "word_count_method": "whitespace_tokens",
        "word_counts": {"title": title_count, "abstract": abstract_count,
                        "manuscript": body_count, "sections": counts},
        "findings": findings,
        "unresolved_research_issues": report["uncertainties"],
        "references": report["references"],
        "human_review_required": True,
        "journal_requirements_verified": False,
        "prose_claim_coverage_verified": False,
        "citation_entailment_verified": False,
        "ethics_or_anonymity_verified": False,
        "independent_verification": False,
        "submission_authorized": False,
        "execution_authorized": False,
    }


def register(app):
    @app.post("/studio/api/research/manuscript-review")
    async def manuscript_review(request: Request):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=786432, timeout_seconds=10.0,
            too_large_detail="Manuscript review too large",
            timeout_detail="Manuscript review timed out", timeout_status=408,
        )
        try:
            result = review(ManuscriptRequest.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid manuscript review", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)
