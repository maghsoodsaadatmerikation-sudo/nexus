"""Opt-in portable research memory snapshots; no server-side persistence."""
from __future__ import annotations
import hashlib
import json
import re
import unicodedata
from typing import Annotated, Literal

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from studio_connections import operator_auth
from studio_research_critique import ClaimId, CritiqueRequest, critique
from studio_research_evidence import clean
from studio_research_graph import NodeId
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class MemoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: NodeId
    note: str = Field(min_length=1, max_length=500)
    reference_draft_sha256: Digest
    claim_ids: list[ClaimId] = Field(min_length=1, max_length=6)


class Snapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal[1] = 1
    project_id: NodeId
    revision: int = Field(ge=0, le=2**53 - 1)
    records: list[MemoryRecord] = Field(default_factory=list, max_length=30)


def digest(snapshot):
    if len({record.id for record in snapshot.records}) != len(snapshot.records):
        raise ValueError("Duplicate memory ID")
    for record in snapshot.records:
        clean(record.note, 500)
        if len(set(record.claim_ids)) != len(record.claim_ids):
            raise ValueError("Duplicate claim reference")
    canonical = json.dumps(snapshot.model_dump(), sort_keys=True, ensure_ascii=True,
                           separators=(",", ":")).encode("ascii")
    return hashlib.sha256(b"nexus-research-memory-v1\x00" + canonical).hexdigest()


class ScopeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    snapshot: Snapshot
    project_id: NodeId
    expected_sha256: Digest


def check_scope(request):
    if request.project_id != request.snapshot.project_id:
        raise ValueError("Project mismatch")
    if digest(request.snapshot) != request.expected_sha256:
        raise ValueError("Snapshot mismatch")


class RecallRequest(ScopeRequest):
    enabled: bool = False
    isolated: bool = False
    query: str = Field(max_length=1000)
    limit: int = Field(default=5, ge=1, le=10)


def terms(value):
    normalized = unicodedata.normalize("NFKC", value).casefold().translate(
        str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک"}))
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    return set(re.findall(r"[^\W_]+", normalized, flags=re.UNICODE))


def recall(request):
    check_scope(request)
    if request.isolated or not request.enabled:
        return {"status": "isolated" if request.isolated else "off", "matches": [],
                "execution_authorized": False}
    clean(request.query, 1000)
    wanted = {term for term in terms(request.query) if 2 <= len(term) <= 80}
    rows = []
    for record in request.snapshot.records:
        score = len(wanted & terms(record.note))
        if score:
            rows.append({"record_id": record.id, "matched_terms": score,
                         "reference_draft_sha256": record.reference_draft_sha256,
                         "claim_ids": record.claim_ids})
    rows.sort(key=lambda row: (-row["matched_terms"], row["record_id"]))
    return {"status": "review_only", "matches": rows[:request.limit],
            "truncated": len(rows) > request.limit,
            "basis": "lexical_overlap_not_verified_relevance",
            "snapshot_sha256": request.expected_sha256, "execution_authorized": False}


class Add(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["add"]
    record: MemoryRecord
    reference: CritiqueRequest


class Remove(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["remove"]
    record_id: NodeId


class Clear(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["clear"]


class ChangeRequest(ScopeRequest):
    consent: bool
    operation: Annotated[Add | Remove | Clear, Field(discriminator="kind")]


def change(request):
    check_scope(request)
    if request.consent is not True:
        raise ValueError("Explicit memory change consent required")
    old = request.snapshot
    records = list(old.records)
    op = request.operation
    if isinstance(op, Add):
        if len(records) >= 30 or any(row.id == op.record.id for row in records):
            raise ValueError("Memory capacity or duplicate record")
        if len(op.reference.perspective_request.model_dump_json().encode("utf-8")) > 262144:
            raise ValueError("Research input budget exceeded")
        checked = critique(op.reference)
        if checked["status"] not in ("reference_draft", "structurally_consistent"):
            raise ValueError("Research draft requires revision")
        if checked["reference_draft_sha256"] != op.record.reference_draft_sha256:
            raise ValueError("Stale reference draft")
        available = {row["claim_id"] for row in checked["reference_draft"]["claims"]}
        if not set(op.record.claim_ids) <= available:
            raise ValueError("Unknown claim reference")
        records.append(op.record)
    elif isinstance(op, Remove):
        records = [row for row in records if row.id != op.record_id]
        if len(records) == len(old.records):
            raise ValueError("Unknown record")
    else:
        records = []
    next_snapshot = Snapshot(project_id=old.project_id, revision=old.revision + 1, records=records)
    return {"status": "snapshot_updated", "snapshot": next_snapshot.model_dump(),
            "snapshot_sha256": digest(next_snapshot), "server_persistence": False,
            "independent_verification": False, "execution_authorized": False}


def register(app):
    @app.post("/studio/api/research/memory/recall")
    async def recall_endpoint(request: Request):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=131072, timeout_seconds=10.0,
            too_large_detail="Memory recall too large",
            timeout_detail="Memory recall timed out", timeout_status=408,
        )
        try:
            result = recall(RecallRequest.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid memory recall", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)

    @app.post("/studio/api/research/memory/change")
    async def change_endpoint(request: Request):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=524288, timeout_seconds=10.0,
            too_large_detail="Memory change too large",
            timeout_detail="Memory change timed out", timeout_status=408,
        )
        try:
            result = change(ChangeRequest.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid memory change", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)
