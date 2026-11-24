"""Structured peer-review checklist over an exact reviewed manuscript.

No semantic judgement, publication recommendation, or automatic closure of
research uncertainties. Reviewer annotations are caller supplied.
"""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_academic import ManuscriptRequest, SectionId, review as review_manuscript
from studio_connections import operator_auth
from studio_research_evidence import clean
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}
CriterionId = Literal[
    "question", "design", "sampling", "measurement", "analysis", "confounding",
    "missing_data", "reproducibility", "logic", "alternative_explanations",
    "scope", "counterevidence", "limitations", "ethics", "disclosures",
    "citation_accuracy",
]
COMMON = (
    "question", "scope", "counterevidence", "limitations", "ethics",
    "disclosures", "citation_accuracy",
)
CRITERIA = {
    "empirical": COMMON + ("design", "sampling", "measurement", "analysis",
                            "confounding", "missing_data", "reproducibility"),
    "conceptual": COMMON + ("logic", "alternative_explanations"),
    "commentary": COMMON + ("logic", "alternative_explanations"),
}
PROMPTS = {
    "question": "Is the research question explicit and appropriately bounded?",
    "design": "Does the design address the stated question and estimand?",
    "sampling": "Are recruitment, selection, sample size and generalizability addressed?",
    "measurement": "Are the measurements, their validity and reliability documented?",
    "analysis": "Are the analyses, assumptions, uncertainty and multiplicity addressed?",
    "confounding": "Are confounding, reverse causality and relevant biases considered?",
    "missing_data": "Are missing observations, exclusions and their handling documented?",
    "reproducibility": "Are methods, data access and analytical procedures sufficiently specified?",
    "logic": "Are premises, intermediate reasoning and conclusions distinguishable?",
    "alternative_explanations": "Are plausible competing accounts and disconfirming observations considered?",
    "scope": "Are population, setting and limits of generalization explicit?",
    "counterevidence": "Are relevant conflicting findings and their contexts represented?",
    "limitations": "Are limitations and unresolved uncertainties disclosed?",
    "ethics": "Are applicable ethics, consent and participant protections addressed?",
    "disclosures": "Are funding, conflicts, contributions and other applicable declarations addressed?",
    "citation_accuracy": "Do cited original sources substantiate the associated claims?",
}


class Annotation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    criterion: CriterionId
    disposition: Literal["reported_addressed", "concern", "not_applicable"]
    section: SectionId | None = None
    start: int | None = Field(default=None, ge=0, le=11999)
    end: int | None = Field(default=None, ge=1, le=12000)
    rationale: str = Field(min_length=1, max_length=1000)


class PeerReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    manuscript: ManuscriptRequest
    manuscript_review_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    annotations: list[Annotation] = Field(default_factory=list, max_length=16)


def digest(domain: bytes, data):
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=True,
                           separators=(",", ":")).encode("ascii")
    return hashlib.sha256(domain + b"\x00" + canonical).hexdigest()


def peer_review(request: PeerReviewRequest):
    checked = review_manuscript(request.manuscript)
    if checked["manuscript_review_sha256"] != request.manuscript_review_sha256:
        raise ValueError("Stale manuscript review")
    applicable = CRITERIA[checked["article_type"]]
    sections = {section.id: section.text for section in request.manuscript.sections}
    observations = {}
    for annotation in request.annotations:
        key = annotation.criterion
        if key not in applicable or key in observations:
            raise ValueError("Invalid or duplicate review criterion")
        clean(annotation.rationale, 1000)
        anchor = None
        span_fields = (annotation.section, annotation.start, annotation.end)
        if any(value is not None for value in span_fields):
            if (any(value is None for value in span_fields)
                    or annotation.section not in sections
                    or annotation.end <= annotation.start
                    or annotation.end > len(sections[annotation.section])):
                raise ValueError("Invalid manuscript span")
            text = sections[annotation.section][annotation.start:annotation.end]
            clean(text, 12000)
            anchor = {
                "section": annotation.section, "start": annotation.start,
                "end": annotation.end, "span_sha256": hashlib.sha256(
                    text.encode("utf-8")).hexdigest(),
            }
        if annotation.disposition == "reported_addressed" and anchor is None:
            raise ValueError("Addressed criteria require an exact manuscript span")
        observations[key] = {
            "disposition": annotation.disposition, "anchor": anchor,
            "rationale_sha256": hashlib.sha256(annotation.rationale.encode("utf-8")).hexdigest(),
        }
    checklist = [
        {"criterion": key, "review_question": PROMPTS[key],
         **observations.get(key, {"disposition": "unreviewed", "anchor": None,
                                  "rationale_sha256": None})}
        for key in applicable
    ]
    # Retain upstream issues unchanged. A caller annotation cannot waive them.
    issues = []
    for finding in checked["findings"]:
        issues.append({"issue_id": "p-" + digest(b"nexus-peer-structure-v1", finding),
                       "origin": "manuscript_structural_review", "finding": finding})
    for uncertainty in checked["unresolved_research_issues"]:
        issues.append({"issue_id": uncertainty["id"],
                       "origin": "research_uncertainty", "finding": uncertainty})
    for item in checklist:
        if item["disposition"] in ("unreviewed", "concern", "not_applicable"):
            key = item["criterion"]
            issues.append({
                "issue_id": "p-" + digest(b"nexus-peer-checklist-v1", key),
                "origin": "review_checklist",
                "finding": {"criterion": key, "disposition": item["disposition"],
                            "review_question": item["review_question"]},
            })
    counts = {key: sum(row["disposition"] == key for row in checklist)
              for key in ("unreviewed", "reported_addressed", "concern", "not_applicable")}
    return {
        "schema_version": 1,
        "peer_review_sha256": digest(b"nexus-peer-review-v1", request.model_dump()),
        "manuscript_review_sha256": checked["manuscript_review_sha256"],
        "article_type": checked["article_type"], "status": "human_review_required",
        "checklist": checklist, "checklist_counts": counts,
        "issues": issues, "issue_count": len(issues),
        "structural_status": checked["status"],
        "limitations": [
            "Checklist dispositions and applicability are caller reports, not independent findings.",
            "Anchors establish only exact text location, not adequacy or truth.",
            "An addressed annotation does not close any upstream research uncertainty.",
            "No scientific validity, ethics compliance, plagiarism, originality or journal fit is determined.",
        ],
        "semantic_verification": False, "independent_verification": False,
        "scientific_validity_verified": False, "publication_recommendation": None,
        "submission_authorized": False, "execution_authorized": False,
    }


def register(app):
    @app.post("/studio/api/research/peer-review")
    async def peer_review_endpoint(request: Request):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=1048576, timeout_seconds=10.0,
            too_large_detail="Peer review too large",
            timeout_detail="Peer review timed out", timeout_status=408)
        try:
            result = peer_review(PeerReviewRequest.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid peer review", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)
