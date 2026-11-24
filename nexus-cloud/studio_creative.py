"""Explicit creative workflows and deterministic text-draft constraint review."""
from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Annotated, Literal

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_connections import operator_auth
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}
Phrase = Annotated[str, Field(min_length=1, max_length=160)]
CandidateId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,31}$")]


class CreativeProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    medium: Literal["literature", "music", "visual_design", "film", "problem_solving"]
    task: Literal["draft", "alternatives", "critique", "revise"]
    alternatives: int = Field(default=3, ge=2, le=5)


MEDIUM = {
    "literature": "Work with voice, narrative coherence, imagery and rhythm.",
    "music": "Work with lyrics, motif, form, dynamics, instrumentation and arrangement as appropriate.",
    "visual_design": "Work with composition, hierarchy, contrast and visual concept.",
    "film": "Work with dramatic structure, scene continuity, framing and sound design.",
    "problem_solving": "Explore distinct feasible approaches and their practical tradeoffs.",
}
TASK = {
    "draft": "Produce the requested original draft or concept.",
    "critique": "Assess the supplied work against the stated goal; identify specific strengths and weaknesses.",
    "revise": "Preserve the user's requested elements and successful earlier choices; revise only where justified.",
}


def creative_policy(base: str, profile: CreativeProfile | None) -> str:
    if profile is None:
        return base
    task = (f"Offer {profile.alternatives} meaningfully distinct approaches, not superficial rewordings."
            if profile.task == "alternatives" else TASK[profile.task])
    return (base + "\nOptional creative workflow for this request: " + MEDIUM[profile.medium]
            + " " + task
            + " Follow the current request and explicit constraints. Distinguish subjective artistic "
              "judgments from factual checks; do not fabricate originality checks or audience reactions. "
              "You can provide text, plans and descriptions only; never claim to have rendered audio, "
              "images, video or files. No additional authority is granted.")


class Brief(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    required_phrases: list[Phrase] = Field(default_factory=list, max_length=20)
    excluded_phrases: list[Phrase] = Field(default_factory=list, max_length=20)
    max_characters: int = Field(default=5000, ge=1, le=24000)


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: CandidateId
    text: str = Field(min_length=1, max_length=24000)


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    brief: Brief
    candidates: list[Candidate] = Field(min_length=1, max_length=5)


def checked_text(value: str) -> str:
    if not value.strip() or any(
        0xD800 <= ord(c) <= 0xDFFF or (ord(c) < 32 and c not in "\n\r\t")
        for c in value
    ):
        raise ValueError("Invalid creative text")
    return unicodedata.normalize("NFC", value).casefold()


def review(request: ReviewRequest):
    required = [checked_text(phrase) for phrase in request.brief.required_phrases]
    excluded = [checked_text(phrase) for phrase in request.brief.excluded_phrases]
    if (len(set(required)) != len(required) or len(set(excluded)) != len(excluded)
            or any(bad in need for need in required for bad in excluded)):
        raise ValueError("Duplicate or conflicting phrase requirements")
    if len({item.id for item in request.candidates}) != len(request.candidates):
        raise ValueError("Duplicate candidate ID")
    rows = []
    seen = {}
    for item in request.candidates:
        normalized = checked_text(item.text)
        missing = [i for i, phrase in enumerate(required) if phrase not in normalized]
        forbidden = [i for i, phrase in enumerate(excluded) if phrase in normalized]
        length = len(item.text)
        over = max(0, length - request.brief.max_characters)
        duplicate = seen.get(normalized)
        seen.setdefault(normalized, item.id)
        rows.append({
            "candidate_id": item.id,
            "text_sha256": hashlib.sha256(item.text.encode("utf-8")).hexdigest(),
            "characters": length,
            "characters_over_limit": over,
            "missing_required_phrase_indices": missing,
            "matched_excluded_phrase_indices": forbidden,
            "duplicate_of": duplicate,
            "literal_constraints_met": not (missing or forbidden or over),
        })
    canonical = json.dumps(request.model_dump(), ensure_ascii=True, sort_keys=True,
                           separators=(",", ":")).encode("ascii")
    return {
        "schema_version": 1,
        "review_sha256": hashlib.sha256(b"nexus-creative-review-v1\x00" + canonical).hexdigest(),
        "candidates": rows,
        "status": "human_artistic_review_required",
        "matching": "NFC_casefold_literal_substring",
        "length_unit": "unicode_code_points",
        "aesthetic_quality_verified": False,
        "originality_verified": False,
        "execution_authorized": False,
    }


def register(app):
    @app.post("/studio/api/creative/review")
    async def creative_review(request: Request):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=524288, timeout_seconds=10.0,
            too_large_detail="Creative review too large",
            timeout_detail="Creative review timed out", timeout_status=408,
        )
        try:
            result = review(ReviewRequest.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid creative review", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)
