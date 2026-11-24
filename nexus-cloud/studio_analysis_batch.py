"""Bounded, deterministic analysis batches; no model, shell, or network dispatch."""
from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_connections import operator_auth
from studio_workflow import Plan, review_plan
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}
StepId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,31}$")]
BoundedInteger = Annotated[int, Field(ge=-10**12, le=10**12)]


class TextMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    step_id: StepId
    operation: Literal["text.metrics"]
    text: str = Field(max_length=12000)


class NumericSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    step_id: StepId
    operation: Literal["numeric.summary"]
    values: list[BoundedInteger] = Field(min_length=1, max_length=1000)


Operation = Annotated[TextMetrics | NumericSummary, Field(discriminator="operation")]


class Batch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    plan: Plan
    operations: list[Operation] = Field(min_length=1, max_length=4)


class ApprovedBatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    batch: Batch
    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    consent: bool


def preview(batch: Batch) -> dict:
    plan = review_plan(batch.plan)
    expected = set(plan["review_order"])
    supplied = [op.step_id for op in batch.operations]
    if (len(set(supplied)) != len(supplied) or set(supplied) != expected
            or any(step.tool != "analysis" for step in batch.plan.steps)):
        raise ValueError("Only fully specified analysis plans are supported")
    for op in batch.operations:
        if isinstance(op, TextMetrics) and any(0xD800 <= ord(c) <= 0xDFFF for c in op.text):
            raise ValueError("Invalid Unicode")
    canonical = json.dumps(batch.model_dump(), sort_keys=True, ensure_ascii=True,
                           separators=(",", ":")).encode("ascii")
    digest = hashlib.sha256(b"nexus-analysis-batch-v1\x00" + canonical).hexdigest()
    ops = {op.step_id: op for op in batch.operations}
    return {
        "schema_version": 1, "review_sha256": digest,
        "plan_sha256": plan["plan_sha256"], "review_order": plan["review_order"],
        "operations": [
            {"step_id": step_id, "operation": ops[step_id].operation,
             "input": ({"text": ops[step_id].text}
                       if isinstance(ops[step_id], TextMetrics)
                       else {"values": ops[step_id].values})}
            for step_id in plan["review_order"]
        ],
        "status": "review_only", "external_execution_authorized": False,
    }


def run(approved: ApprovedBatch) -> dict:
    reviewed = preview(approved.batch)
    if approved.consent is not True or approved.review_sha256 != reviewed["review_sha256"]:
        raise ValueError("Changed or unapproved analysis batch")
    ops = {op.step_id: op for op in approved.batch.operations}
    results = []
    for step_id in reviewed["review_order"]:
        op = ops[step_id]
        if isinstance(op, TextMetrics):
            metrics = {"characters": len(op.text), "utf8_bytes": len(op.text.encode("utf-8")),
                       "whitespace_tokens": len(op.text.split()),
                       "lines": len(op.text.splitlines())}
        else:
            values = sorted(op.values)
            count = len(values)
            middle = count // 2
            median = (values[middle] if count % 2
                      else (values[middle - 1] + values[middle]) / 2)
            metrics = {"count": count, "sum": sum(values), "min": values[0],
                       "max": values[-1], "mean": sum(values) / count, "median": median}
        results.append({"step_id": step_id, "operation": op.operation, "metrics": metrics})
    return {
        "schema_version": 1, "review_sha256": reviewed["review_sha256"],
        "status": "computed", "results": results,
        "evidence": "deterministic_analysis_of_supplied_input",
        "external_execution_authorized": False,
    }


def register(app):
    async def read(request):
        operator_auth(request)
        return await read_bounded_body(
            request, max_bytes=65536, timeout_seconds=10.0,
            too_large_detail="Analysis batch too large",
            timeout_detail="Analysis batch timed out", timeout_status=408,
        )

    @app.post("/studio/api/analysis-batch/review")
    async def review_endpoint(request: Request):
        body = await read(request)
        try:
            result = preview(Batch.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid analysis batch", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)

    @app.post("/studio/api/analysis-batch/run")
    async def run_endpoint(request: Request):
        body = await read(request)
        try:
            result = run(ApprovedBatch.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid or changed analysis batch", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)
