"""Compare manuscript structure against caller-supplied journal policy snapshots."""
from __future__ import annotations

from datetime import date
from typing import Annotated, Literal
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_academic import ManuscriptRequest, SectionId, review
from studio_connections import operator_auth
from studio_peer_review import digest
from studio_research_evidence import clean
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}
ArticleType = Literal["empirical", "conceptual", "commentary"]
Tag = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,39}$")]
Currency = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]


class Fee(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    # Currency and amount are explicit minor units, not inferred from symbols.
    currency: Currency
    amount_minor: int = Field(ge=0, le=10**9)


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    journal_id: Tag
    name: str = Field(min_length=1, max_length=200)
    policy_url: str = Field(min_length=1, max_length=1000)
    policy_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    accepted_article_types: list[ArticleType] | None = Field(default=None, max_length=3)
    topic_tags: list[Tag] | None = Field(default=None, max_length=20)
    title_word_limit: int | None = Field(default=None, ge=1, le=200)
    abstract_word_limit: int | None = Field(default=None, ge=1, le=2000)
    abstract_required: bool | None = None
    main_text_word_limit: int | None = Field(default=None, ge=1, le=20000)
    required_sections: list[SectionId] | None = Field(default=None, max_length=8)
    mandatory_publication_fee: Fee | None = None
    anonymized_review_required: bool | None = None


class JournalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    manuscript: ManuscriptRequest
    manuscript_review_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    manuscript_topic_tags: list[Tag] = Field(default_factory=list, max_length=20)
    policies: list[Policy] = Field(min_length=1, max_length=12)
    fee_budget: Fee | None = None


def validate_policy(policy: Policy):
    clean(policy.name, 200)
    date.fromisoformat(policy.policy_date)
    url = policy.policy_url
    if any(ord(c) <= 32 or ord(c) == 127 for c in url) or "\\" in url:
        raise ValueError("Invalid policy URL")
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.port not in (None, 443)):
        raise ValueError("Invalid policy URL")
    for values in (policy.accepted_article_types, policy.topic_tags, policy.required_sections):
        if values is not None and len(set(values)) != len(values):
            raise ValueError("Duplicate policy value")
    if policy.abstract_required is False and policy.required_sections is not None and "abstract" in policy.required_sections:
        raise ValueError("Inconsistent abstract policy")


def compare(request: JournalRequest):
    checked = review(request.manuscript)
    if checked["manuscript_review_sha256"] != request.manuscript_review_sha256:
        raise ValueError("Stale manuscript review")
    if len(set(request.manuscript_topic_tags)) != len(request.manuscript_topic_tags):
        raise ValueError("Duplicate manuscript topic")
    if len({p.journal_id for p in request.policies}) != len(request.policies):
        raise ValueError("Duplicate journal")
    counts = checked["word_counts"]
    sections = set(counts["sections"])
    # Fixed counting convention; policy snapshots must use this convention.
    main_words = sum(count for key, count in counts["sections"].items()
                     if key not in ("abstract", "declarations"))
    rows = []
    for policy in request.policies:
        validate_policy(policy)
        checks = []

        def add(field, outcome, **details):
            checks.append({"field": field, "outcome": outcome, **details})

        types = policy.accepted_article_types
        add("article_type", "unknown" if types is None else
            "matches_reported_rule" if checked["article_type"] in types else "mismatch")
        for field, actual, limit in (
            ("title_words", counts["title"], policy.title_word_limit),
            ("abstract_words", counts["abstract"], policy.abstract_word_limit),
            ("main_text_words", main_words, policy.main_text_word_limit),
        ):
            add(field, "unknown" if limit is None else
                "matches_reported_rule" if actual <= limit else "mismatch",
                actual=actual, limit=limit)
        add("abstract_required", "unknown" if policy.abstract_required is None else
            "mismatch" if policy.abstract_required and "abstract" not in sections else
            "matches_reported_rule")
        missing = (None if policy.required_sections is None else
                   sorted(set(policy.required_sections) - sections))
        add("required_sections", "unknown" if missing is None else
            "mismatch" if missing else "matches_reported_rule", missing=missing)
        topics = sorted(set(request.manuscript_topic_tags) & set(policy.topic_tags or []))
        add("topic_tags", "unknown" if policy.topic_tags is None or not request.manuscript_topic_tags else
            "literal_overlap" if topics else "no_literal_overlap", shared_tags=topics)
        fee, budget = policy.mandatory_publication_fee, request.fee_budget
        if fee is None:
            fee_status = "unknown"
        elif budget is None:
            fee_status = "budget_not_supplied"
        elif fee.currency != budget.currency:
            fee_status = "currency_not_comparable"
        else:
            fee_status = "matches_reported_rule" if fee.amount_minor <= budget.amount_minor else "mismatch"
        add("mandatory_publication_fee", fee_status,
            reported_fee=fee.model_dump() if fee else None)
        add("anonymized_review", "manual_review_required" if policy.anonymized_review_required is not None else "unknown",
            reported_required=policy.anonymized_review_required)
        rows.append({
            "journal_id": policy.journal_id, "name": policy.name,
            "policy_url": policy.policy_url, "policy_date": policy.policy_date,
            "policy_origin": "caller_supplied_unverified",
            "checks": checks,
            "mismatch_count": sum(c["outcome"] == "mismatch" for c in checks),
            "status": "reported_mismatch" if any(c["outcome"] == "mismatch" for c in checks)
                      else "manual_review_required",
        })
    return {
        "schema_version": 1,
        "journal_review_sha256": digest(b"nexus-journal-policy-v1", request.model_dump()),
        "manuscript_review_sha256": checked["manuscript_review_sha256"],
        "status": "human_review_required", "journals": rows,
        "word_count_method": "whitespace_tokens_main_text_excludes_abstract_declarations_title_references",
        "upstream_findings": checked["findings"],
        "unresolved_research_issues": checked["unresolved_research_issues"],
        "limitations": [
            "Journal policies, fees, dates and topic labels are caller supplied and not retrieved or authenticated.",
            "Word counting rules vary by journal; only the stated fixed counting convention is implemented.",
            "A topic-tag overlap is not a semantic scope or suitability assessment.",
            "Unknown fees are not free; no exchange rates, optional fees or waiver eligibility are inferred.",
            "No journal ranking, indexing, legitimacy, acceptance probability, anonymity or submission readiness is verified.",
        ],
        "policy_verified": False, "scope_verified": False,
        "anonymity_verified": False, "submission_authorized": False,
        "execution_authorized": False,
    }


def register(app):
    @app.post("/studio/api/research/journal-review")
    async def journal_review(request: Request):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=1048576, timeout_seconds=10.0,
            too_large_detail="Journal review too large",
            timeout_detail="Journal review timed out", timeout_status=408)
        try:
            result = compare(JournalRequest.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid journal review", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)
