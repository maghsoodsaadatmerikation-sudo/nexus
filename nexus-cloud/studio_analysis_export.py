"""Download bounded analysis reports after a fresh consistency check."""
from __future__ import annotations

import csv
import hashlib
import html
import io
import json
from typing import Literal

from fastapi import HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, ValidationError

from studio_analysis_audit import AuditRequest, audit
from studio_analysis_batch import ApprovedBatch, run
from studio_office_report import docx, xlsx
from studio_connections import operator_auth
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}
MAX_EXPORT = 128 * 1024


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    approved: ApprovedBatch
    format: Literal["json", "csv", "html", "xlsx", "docx"]
    export_consent: bool


class InconsistentResult(ValueError):
    """Computed result failed the separate consistency check."""


def report_rows(result):
    for step in result["results"]:
        for metric, value in step["metrics"].items():
            yield (step["step_id"], step["operation"], "metric", metric, value, "", "")
        for ref in step.get("input_provenance", []):
            yield (step["step_id"], step["operation"], "input", "", ref["value"],
                   ref["step_id"], ref["metric"])


COLUMNS = ("step_id", "operation", "kind", "metric", "value", "source_step", "source_metric")


def build_export(request: ExportRequest):
    if request.export_consent is not True:
        raise ValueError("Explicit export consent required")
    computed = run(request.approved)
    checked = audit(AuditRequest(approved=request.approved, candidate=computed))
    if checked["status"] != "consistent":
        raise InconsistentResult("Analysis consistency check failed")
    report = {
        "schema_version": 1,
        "review_sha256": computed["review_sha256"],
        "evidence": "bounded_recomputation_of_supplied_input",
        "consistency": "consistent",
        "external_execution_authorized": False,
        "results": computed["results"],
    }
    if request.format == "json":
        data = (json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2,
                           allow_nan=False) + "\n").encode("utf-8")
        media = "application/json"
    elif request.format == "csv":
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\r\n")
        writer.writerow(("review_sha256", "consistency", *COLUMNS))
        # All string cells originate in fixed enums or validated letter-first IDs.
        # No raw plan or user-provided prose can become a spreadsheet formula.
        for row in report_rows(computed):
            writer.writerow((report["review_sha256"], "consistent", *row))
        data = stream.getvalue().encode("utf-8")
        media = "text/csv; charset=utf-8"
    elif request.format in ("xlsx", "docx"):
        rows = list(report_rows(computed))
        if request.format == "xlsx":
            data = xlsx(report["review_sha256"], COLUMNS, rows)
            media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            data = docx(report["review_sha256"], COLUMNS, rows)
            media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        def cell(value):
            return html.escape(str(value), quote=True)
        headings = "".join(f"<th>{cell(key)}</th>" for key in COLUMNS)
        rows = "".join("<tr>" + "".join(f"<td>{cell(value)}</td>" for value in row)
                       + "</tr>" for row in report_rows(computed))
        data = (
            '<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'">'
            '<title>NEXUS analysis report</title></head><body>'
            '<h1>NEXUS analysis report</h1>'
            '<p>Computational consistency: consistent. Supplied inputs only; '
            'not independent source verification or human approval.</p>'
            f'<p>Review SHA-256: <code>{cell(report["review_sha256"])}</code></p>'
            f'<table><thead><tr>{headings}</tr></thead><tbody>{rows}</tbody></table>'
            '</body></html>'
        ).encode("utf-8")
        media = "text/html; charset=utf-8"
    if len(data) > MAX_EXPORT:
        raise ValueError("Export exceeded output bound")
    return data, media


def register(app):
    @app.post("/studio/api/analysis-batch/export")
    async def export_endpoint(request: Request):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=65536, timeout_seconds=10.0,
            too_large_detail="Analysis export too large",
            timeout_detail="Analysis export timed out", timeout_status=408,
        )
        try:
            export = ExportRequest.model_validate_json(body)
            data, media = build_export(export)
        except InconsistentResult:
            raise HTTPException(409, "Analysis consistency check failed", headers=NO_STORE) from None
        except (ValidationError, ValueError, RecursionError, OverflowError):
            raise HTTPException(422, "Invalid analysis export", headers=NO_STORE) from None
        return Response(data, media_type=media, headers={
            **NO_STORE,
            "Content-Disposition": f'attachment; filename="nexus-analysis.{export.format}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'",
            "X-Nexus-Content-SHA256": hashlib.sha256(data).hexdigest(),
        })
