"""Explicit plain-text manuscript redaction, not a guarantee of anonymity."""
from __future__ import annotations

import re
from typing import Literal

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_connections import operator_auth
from studio_peer_review import digest
from studio_research_evidence import clean
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}
PartId = Literal["title", "abstract", "introduction", "methods", "results", "discussion",
                 "limitations", "conclusion", "declarations", "acknowledgements", "funding",
                 "author_details", "references", "headers", "footers", "metadata_text"]
Category = Literal["name", "institution", "self_citation", "funding", "identifier", "other"]
MARKER = "[REDACTED]"
MAX_MATCHES = 2000
PATTERNS = {
    "email_pattern": re.compile(
        r"(?<![\w.+-])[A-Za-z0-9.!#$%&'*+/=?^_{}~-]{1,64}"
        r"@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63}){1,5}(?![\w-]|\.[A-Za-z0-9-])"),
    "orcid_pattern": re.compile(
        r"(?<!\w)(?:https?://orcid\.org/)?[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X](?!\w)",
        re.IGNORECASE),
    "nct_registration_pattern": re.compile(r"(?<!\w)NCT[0-9]{8}(?!\w)", re.IGNORECASE),
}


class Part(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: PartId
    text: str = Field(min_length=1, max_length=12000)


class LiteralRule(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    category: Category
    text: str = Field(min_length=2, max_length=200)
    case_sensitive: bool = False


class RedactionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    parts: list[Part] = Field(min_length=1, max_length=16)
    literal_rules: list[LiteralRule] = Field(default_factory=list, max_length=32)
    remove_parts: list[PartId] = Field(default_factory=list, max_length=16)
    scan_email: bool = True
    scan_orcid: bool = True
    scan_nct_registration: bool = False


class ApprovedRedaction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    plan: RedactionPlan
    review_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    consent: bool = False


def rules(plan):
    patterns = []
    for rule in plan.literal_rules:
        clean(rule.text, 200)
        flags = 0 if rule.case_sensitive else re.IGNORECASE
        # Lookahead captures overlapping literal occurrences, including when
        # the same identifier overlaps itself. Caller text is never regex code.
        patterns.append((rule.category, re.compile("(?=(" + re.escape(rule.text) + "))", flags), 1))
    for category, enabled in (
        ("email_pattern", plan.scan_email),
        ("orcid_pattern", plan.scan_orcid),
        ("nct_registration_pattern", plan.scan_nct_registration),
    ):
        if enabled:
            patterns.append((category, PATTERNS[category], 0))
    return patterns


def spans(text, patterns, remaining):
    raw = []
    for category, pattern, group in patterns:
        for match in pattern.finditer(text):
            start, end = match.span(group)
            raw.append((start, end, category))
            if len(raw) > remaining:
                raise ValueError("Too many redaction matches; narrow the review")
    merged = []
    for start, end, category in sorted(raw):
        if merged and start <= merged[-1]["end"]:
            merged[-1]["end"] = max(end, merged[-1]["end"])
            if category not in merged[-1]["categories"]:
                merged[-1]["categories"].append(category)
        else:
            merged.append({"start": start, "end": end, "categories": [category]})
    for row in merged:
        row["categories"].sort()
    return merged, len(raw)


def preview(plan: RedactionPlan):
    ids = [p.id for p in plan.parts]
    if len(set(ids)) != len(ids) or len(set(plan.remove_parts)) != len(plan.remove_parts):
        raise ValueError("Duplicate part")
    if not set(plan.remove_parts) <= set(ids):
        raise ValueError("Unknown removal target")
    if set(plan.remove_parts) == set(ids):
        raise ValueError("Cannot remove every part")
    patterns = rules(plan)
    rows = []
    total = 0
    for part in plan.parts:
        clean(part.text, 12000)
        removed = part.id in plan.remove_parts
        matches, count = ([], 0) if removed else spans(part.text, patterns, MAX_MATCHES-total)
        total += count
        rows.append({"part": part.id, "remove_entire_part": removed,
                     "spans": matches, "raw_match_count": count})
    return {
        "schema_version": 1,
        "review_sha256": digest(b"nexus-academic-redaction-v1", plan.model_dump()),
        "status": "review_only",
        "parts": rows,
        "raw_match_count": total,
        "offset_convention": "unicode_code_points_start_inclusive_end_exclusive",
        "anonymity_verified": False,
        "execution_authorized": False,
    }


def run(approved: ApprovedRedaction):
    checked = preview(approved.plan)
    if approved.consent is not True or approved.review_sha256 != checked["review_sha256"]:
        raise ValueError("Changed or unapproved redaction plan")
    patterns = rules(approved.plan)
    by_id = {part.id: part.text for part in approved.plan.parts}
    output, remaining_findings = [], []
    total = 0
    for row in checked["parts"]:
        if row["remove_entire_part"]:
            continue
        text = by_id[row["part"]]
        pieces = []
        cursor = 0
        for span in row["spans"]:
            pieces.extend((text[cursor:span["start"]], MARKER))
            cursor = span["end"]
        pieces.append(text[cursor:])
        redacted = "".join(pieces)
        # Recheck the actual output, including newly formed boundaries and
        # replacement markers. Never claim success if the same rule still matches.
        matches, count = spans(redacted, patterns, MAX_MATCHES-total)
        total += count
        if matches:
            remaining_findings.append({"part": row["part"], "spans": matches})
        output.append({"id": row["part"], "text": redacted})
    return {
        "schema_version": 1, "review_sha256": checked["review_sha256"],
        "status": "remaining_rule_matches" if remaining_findings else "redacted_draft_requires_manual_review",
        "parts": output, "removed_parts": list(approved.plan.remove_parts),
        "remaining_rule_matches": remaining_findings,
        "limitations": [
            "Only supplied plain-text parts are processed; no actual document file or hidden metadata is inspected.",
            "Literal matching is not semantic identity detection and does not normalize Unicode or resolve spelling variants.",
            "Email, ORCID and NCT patterns are limited syntax heuristics, not verified identifiers.",
            "Names, affiliations, self-citations, funding, dates and indirect identifiers may remain if not supplied as rules.",
            "A zero residual-match count does not establish anonymity or journal compliance.",
            "Review digests bind inputs but are not encryption or proof of authorization by themselves.",
        ],
        "anonymity_verified": False, "journal_compliance_verified": False,
        "document_metadata_inspected": False, "submission_authorized": False,
        "execution_authorized": False,
    }


def register(app):
    async def parse(request, schema, function):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=1048576, timeout_seconds=10.0,
            too_large_detail="Redaction request too large",
            timeout_detail="Redaction request timed out", timeout_status=408)
        try:
            result = function(schema.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid redaction request", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)

    @app.post("/studio/api/research/anonymization/review")
    async def review_endpoint(request: Request):
        return await parse(request, RedactionPlan, preview)

    @app.post("/studio/api/research/anonymization/run")
    async def run_endpoint(request: Request):
        return await parse(request, ApprovedRedaction, run)
