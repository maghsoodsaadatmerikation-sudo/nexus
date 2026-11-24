"""Recompute bounded analysis results and identify discrepancies without external authority."""
from __future__ import annotations

import math
import statistics
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, ValidationError

from studio_analysis_batch import ApprovedBatch, NumericSummary, TextMetrics, preview
from studio_connections import operator_auth
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}
MAX_FINDINGS = 32


class AuditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    approved: ApprovedBatch
    candidate: dict[str, Any]


def recompute(approved: ApprovedBatch) -> dict:
    """Separate numerical implementation; shares the input schema and plan review."""
    reviewed = preview(approved.batch)
    if approved.consent is not True or approved.review_sha256 != reviewed["review_sha256"]:
        raise ValueError("Changed or unapproved batch")
    ops = {op.step_id: op for op in approved.batch.operations}
    verified = {}
    results = []
    for step_id in reviewed["review_order"]:
        op = ops[step_id]
        row = {"step_id": step_id, "operation": op.operation}
        if isinstance(op, TextMetrics):
            text = op.text
            metrics = {
                "characters": sum(1 for _ in text),
                "utf8_bytes": len(text.encode("utf-8")),
                "whitespace_tokens": len(text.split()),
                "lines": len(text.splitlines()),
            }
        else:
            if isinstance(op, NumericSummary):
                values = op.values
            else:
                values = [verified[ref.step_id][ref.metric] for ref in op.references]
                if any(type(value) is not int or abs(value) > 10**12 for value in values):
                    raise ValueError("Referenced metric exceeds input bounds")
                row["input_provenance"] = [
                    {"step_id": ref.step_id, "metric": ref.metric, "value": value}
                    for ref, value in zip(op.references, values)
                ]
            metrics = {
                "count": len(values), "sum": sum(values),
                "min": min(values), "max": max(values),
                "mean": float(statistics.mean(values)),
                "median": statistics.median(values),
            }
        row["metrics"] = metrics
        verified[step_id] = metrics
        results.append(row)
    return {
        "schema_version": 1, "review_sha256": reviewed["review_sha256"],
        "status": "computed", "results": results,
        "evidence": "deterministic_analysis_of_supplied_input",
        "external_execution_authorized": False,
    }


def audit(request: AuditRequest) -> dict:
    expected = recompute(request.approved)
    findings = []
    total = 0

    def flag(path, code):
        nonlocal total
        total += 1
        if len(findings) < MAX_FINDINGS:
            findings.append({"path": path, "code": code})

    def compare(wanted, actual, path):
        # JSON booleans must never pass as integers. For expected float metrics,
        # accept equivalent finite numeric JSON representations only.
        if isinstance(wanted, float):
            if type(actual) not in (int, float):
                flag(path, "type_mismatch")
            elif actual != wanted or (type(actual) is float and not math.isfinite(actual)):
                flag(path, "value_mismatch")
            return
        if type(wanted) is not type(actual):
            flag(path, "type_mismatch")
            return
        if isinstance(wanted, dict):
            for key, value in wanted.items():
                if key not in actual:
                    flag(f"{path}.{key}", "missing_field")
                else:
                    compare(value, actual[key], f"{path}.{key}")
            if actual.keys() - wanted.keys():
                # Do not reflect caller-controlled extra field names or data.
                flag(path, "unexpected_fields")
        elif isinstance(wanted, list):
            if len(wanted) != len(actual):
                flag(path, "length_mismatch")
            for index, (value, item) in enumerate(zip(wanted, actual)):
                compare(value, item, f"{path}[{index}]")
        elif wanted != actual:
            flag(path, "value_mismatch")

    compare(expected, request.candidate, "$")
    result = {
        "schema_version": 1, "review_sha256": expected["review_sha256"],
        "status": "mismatch" if total else "consistent",
        "findings": findings, "finding_count": total,
        "findings_truncated": total > MAX_FINDINGS,
        "evidence": "bounded_recomputation_of_supplied_input",
        "external_execution_authorized": False,
    }
    if total:
        result["recomputed_result"] = expected
    return result


def register(app):
    @app.post("/studio/api/analysis-batch/audit")
    async def audit_endpoint(request: Request):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=98304, timeout_seconds=10.0,
            too_large_detail="Analysis audit too large",
            timeout_detail="Analysis audit timed out", timeout_status=408,
        )
        try:
            result = audit(AuditRequest.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError, OverflowError):
            raise HTTPException(422, "Invalid analysis audit", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)
