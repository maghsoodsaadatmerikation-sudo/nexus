"""Compare two exact peer-reviewed manuscript versions and track author replies."""
from __future__ import annotations

import hashlib
from typing import Literal

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_academic import SectionId
from studio_connections import operator_auth
from studio_peer_review import PeerReviewRequest, peer_review, digest
from studio_research_evidence import clean
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}


class AuthorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    issue_id: str = Field(pattern=r"^[pu]-[a-f0-9]{64}$")
    action: Literal["revised", "clarified", "disagree", "deferred"]
    response: str = Field(min_length=1, max_length=1500)
    section: SectionId | None = None
    start: int | None = Field(default=None, ge=0, le=11999)
    end: int | None = Field(default=None, ge=1, le=12000)


class RevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    previous: PeerReviewRequest
    previous_peer_review_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    current: PeerReviewRequest
    current_peer_review_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    responses: list[AuthorResponse] = Field(default_factory=list, max_length=100)
    include_response_text: bool = False


def compare(request: RevisionRequest):
    previous = peer_review(request.previous)
    current = peer_review(request.current)
    if (previous["peer_review_sha256"] != request.previous_peer_review_sha256
            or current["peer_review_sha256"] != request.current_peer_review_sha256):
        raise ValueError("Stale peer review")
    before = {s.id: s for s in request.previous.manuscript.sections}
    after = {s.id: s for s in request.current.manuscript.sections}
    changes = []
    for key in dict.fromkeys([*before, *after]):
        old, new = before.get(key), after.get(key)
        if old is None:
            status = "added"
        elif new is None:
            status = "removed"
        elif old == new:
            status = "unchanged"
        else:
            status = "changed"
        changes.append({
            "section": key, "status": status,
            "text_changed": old is None or new is None or old.text != new.text,
            "citation_mapping_changed": old is None or new is None or old.citations != new.citations,
            "previous_section_sha256": digest(b"nexus-revision-section-v1", old.model_dump()) if old else None,
            "current_section_sha256": digest(b"nexus-revision-section-v1", new.model_dump()) if new else None,
        })
    by_section = {row["section"]: row for row in changes}
    old_issues = {row["issue_id"]: row for row in previous["issues"]}
    new_issues = {row["issue_id"]: row for row in current["issues"]}
    if len(old_issues) != len(previous["issues"]) or len(new_issues) != len(current["issues"]):
        raise ValueError("Ambiguous issue identity")
    responses = {}
    for reply in request.responses:
        if reply.issue_id not in old_issues or reply.issue_id in responses:
            raise ValueError("Unknown or duplicate issue response")
        clean(reply.response, 1500)
        anchor = None
        span_fields = (reply.section, reply.start, reply.end)
        if any(value is not None for value in span_fields):
            if (any(value is None for value in span_fields) or reply.section not in after
                    or reply.end <= reply.start or reply.end > len(after[reply.section].text)):
                raise ValueError("Invalid revision anchor")
            text = after[reply.section].text[reply.start:reply.end]
            clean(text, 12000)
            anchor = {
                "section": reply.section, "start": reply.start, "end": reply.end,
                "span_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        if reply.action in ("revised", "clarified") and anchor is None:
            raise ValueError("Revision and clarification require a current text anchor")
        if reply.action == "revised":
            if not by_section[reply.section]["text_changed"]:
                raise ValueError("Reported revision must point to changed section text")
            old_section = before.get(reply.section)
            if old_section is not None and text in old_section.text:
                raise ValueError("Revision anchor must identify text not present in old section")
        row = {
            "action": reply.action, "anchor": anchor,
            "response_sha256": hashlib.sha256(reply.response.encode("utf-8")).hexdigest(),
            "author_reported_only": True,
        }
        if request.include_response_text:
            row["author_response_draft"] = reply.response
        responses[reply.issue_id] = row
    ledger = []
    for key, old in old_issues.items():
        new = new_issues.get(key)
        ledger.append({
            "issue_id": key, "previous_issue": old, "current_issue": new,
            "status": ("not_reported_in_current_review" if new is None else
                       "persisting_unchanged" if old == new else "persisting_changed"),
            "author_response": responses.get(key),
            "resolution_verified": False,
        })
    for key, new in new_issues.items():
        if key not in old_issues:
            ledger.append({"issue_id": key, "previous_issue": None, "current_issue": new,
                           "status": "newly_reported", "author_response": None,
                           "resolution_verified": False})
    statuses = ("not_reported_in_current_review", "persisting_unchanged",
                "persisting_changed", "newly_reported")
    return {
        "schema_version": 1,
        "revision_review_sha256": digest(b"nexus-manuscript-revision-v1", request.model_dump()),
        "previous_peer_review_sha256": previous["peer_review_sha256"],
        "current_peer_review_sha256": current["peer_review_sha256"],
        "status": "human_review_required",
        "title_changed": request.previous.manuscript.title != request.current.manuscript.title,
        "article_type_changed": previous["article_type"] != current["article_type"],
        "synthesis_changed": request.previous.manuscript.report_sha256 != request.current.manuscript.report_sha256,
        "section_order_changed": list(before) != list(after),
        "sections": changes, "issue_ledger": ledger,
        "issue_counts": {status: sum(row["status"] == status for row in ledger) for status in statuses},
        "previous_issues_without_author_response": [key for key in old_issues if key not in responses],
        "response_text_included": request.include_response_text,
        "limitations": [
            "Issue IDs are structural identifiers; a changed ID may represent a related issue.",
            "An issue absent from the current report is not necessarily resolved.",
            "A new text anchor does not establish adequacy of a revision.",
            "Author replies are caller supplied, not reviewer acceptance or independent verification.",
        ],
        "scientific_validity_verified": False, "independent_verification": False,
        "reviewer_acceptance_verified": False, "submission_authorized": False,
        "execution_authorized": False,
    }


def register(app):
    @app.post("/studio/api/research/revision-review")
    async def revision_endpoint(request: Request):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=2097152, timeout_seconds=10.0,
            too_large_detail="Revision review too large",
            timeout_detail="Revision review timed out", timeout_status=408)
        try:
            result = compare(RevisionRequest.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid revision review", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)
