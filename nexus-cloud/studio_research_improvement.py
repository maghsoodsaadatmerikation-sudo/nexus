"""Consent-gated structural repair and bounded re-review of research drafts."""
from __future__ import annotations

import hashlib
import json

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_connections import operator_auth
from studio_research_critique import CritiqueRequest, Draft, critique
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}


class ImprovementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    review: CritiqueRequest
    reference_draft_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    repair_consent: bool = False


def draft_digest(draft: Draft, reference: str) -> str:
    canonical = json.dumps(draft.model_dump(), sort_keys=True, ensure_ascii=True,
                           separators=(",", ":")).encode("ascii")
    return hashlib.sha256(b"nexus-improvement-candidate-v1\x00"
                          + reference.encode("ascii") + b"\x00" + canonical).hexdigest()


def improve(request: ImprovementRequest):
    if request.review.candidate is None:
        raise ValueError("An initial draft is required")
    if len(request.review.perspective_request.model_dump_json().encode("utf-8")) > 262144:
        raise ValueError("Research input budget exceeded")
    before = critique(request.review)
    reference = before["reference_draft_sha256"]
    if reference != request.reference_draft_sha256:
        raise ValueError("Stale reference draft")
    initial = request.review.candidate
    initial_hash = draft_digest(initial, reference)
    result = {
        "schema_version": 1,
        "reference_draft_sha256": reference,
        "initial_candidate_sha256": initial_hash,
        "initial_finding_count": before["finding_count"],
        "initial_findings": before["findings"],
        "initial_findings_truncated": before["findings_truncated"],
        "repair_applied_to_returned_draft": False,
        "repair_rounds": 0,
        "final_candidate_sha256": initial_hash,
        "final_finding_count": before["finding_count"],
        "final_draft": None,
        "status": "repair_consent_required",
        "human_review_required": True,
        "semantic_verification": False,
        "independent_verification": False,
        "execution_authorized": False,
        "server_persistence": False,
    }
    if before["status"] == "structurally_consistent":
        result.update(status="already_consistent", final_draft=initial.model_dump())
        return result
    if not request.repair_consent:
        return result
    # The draft contains only the reviewed structural fields, not free prose.
    # Reconstruct all fields, rather than applying incomplete/truncated findings.
    repaired = Draft.model_validate(before["reference_draft"])
    after = critique(request.review.model_copy(update={"candidate": repaired}))
    if (after["reference_draft_sha256"] != reference
            or after["status"] != "structurally_consistent"
            or after["finding_count"] != 0):
        result["status"] = "repair_rejected"
        return result
    result.update(
        status="structural_repair_consistent",
        repair_applied_to_returned_draft=True,
        repair_rounds=1,
        final_candidate_sha256=draft_digest(repaired, reference),
        final_finding_count=after["finding_count"],
        final_draft=repaired.model_dump(),
    )
    return result


def register(app):
    @app.post("/studio/api/research/improvement")
    async def improvement_endpoint(request: Request):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=393216, timeout_seconds=10.0,
            too_large_detail="Research improvement too large",
            timeout_detail="Research improvement timed out", timeout_status=408,
        )
        try:
            result = improve(ImprovementRequest.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid research improvement", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)
