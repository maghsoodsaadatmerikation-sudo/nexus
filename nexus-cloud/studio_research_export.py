"""Portable research report exports bound to a freshly recomputed synthesis."""
from __future__ import annotations

import hashlib
import html
import json
from typing import Literal

from fastapi import HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_connections import operator_auth
from studio_research_synthesis import SynthesisRequest, synthesize
from transport_bounds import read_bounded_body

MAX_EXPORT = 512 * 1024
NO_STORE = {"Cache-Control": "no-store"}
CSP = "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    synthesis: SynthesisRequest
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    format: Literal["json", "html"]
    export_consent: bool = False


def escape(value):
    return html.escape(str(value), quote=True)


def table(headings, rows):
    return ("<table><thead><tr>" +
            "".join(f'<th scope="col">{escape(x)}</th>' for x in headings) +
            "</tr></thead><tbody>" +
            "".join("<tr>" + "".join(f'<td dir="auto">{escape(x)}</td>' for x in row)
                    + "</tr>" for row in rows) + "</tbody></table>")


def join(values):
    return ", ".join(str(value) for value in values) or "None"


def render_html(report):
    # Display untrusted content only as escaped text; no active source links.
    # Keep a complete machine-readable copy visible in a native details panel.
    claim_rows = []
    for row in report["claims"]:
        claim_rows.append((row["claim_id"], row.get("caller_supplied_claim", "[Not included]"),
                           row["claim_kind"], row["status"],
                           join(f'[{link["reference_number"]}] {link["relation"]}'
                                + (" (metadata only)" if link["metadata_only"] else "")
                                for link in row["reference_links"])))
    ref_rows = [(row["number"], row["title"] or "[Conflicting titles — review required]",
                 row["url"], join(row["missing_metadata"]),
                 join(row["conflicting_titles"])) for row in report["references"]]
    uncertainty_rows = [(row["category"], row["code"], join(row["target"]),
                         row["review_action"], row["status"]) for row in report["uncertainties"]]
    comparison_rows = [(row["left_claim_id"], row["right_claim_id"], row["status"],
                         join(row["different_scope_fields"]), join(row["unknown_scope_fields"]))
                        for row in report["claim_comparisons"]]
    view_rows = [(row["id"], row["label"], join(row["claim_ids"]))
                 for row in report["perspectives"]]
    limitations = "".join(f"<li>{escape(item)}</li>" for item in report["limitations"])
    complete = escape(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="' + escape(CSP) + '">'
        '<title>NEXUS research synthesis draft</title>'
        '<style>body{font:16px/1.5 system-ui,sans-serif;color:#19212c;background:#fff;'
        'max-width:1000px;margin:2rem auto;padding:0 1rem}h1,h2{line-height:1.2}'
        'table{width:100%;border-collapse:collapse;font-size:.9rem}'
        'th,td{padding:.55rem;border:1px solid #cbd3dc;text-align:left;vertical-align:top;'
        'overflow-wrap:anywhere}th{background:#edf1f5}pre,code{overflow-wrap:anywhere;'
        'white-space:pre-wrap}section{margin:2rem 0}.scroll{overflow-x:auto}'
        '@media print{body{margin:0;max-width:none}tr{break-inside:avoid}}</style></head><body>'
        '<h1>NEXUS research synthesis draft</h1>'
        '<p><strong>Human review required — not a verified scientific conclusion.</strong></p>'
        '<p>Report SHA-256: <code>' + escape(report["report_sha256"]) + '</code></p>'
        '<section><h2>Limitations</h2><ul>' + limitations + '</ul></section>'
        '<section><h2>Claims and evidence</h2><div class="scroll">' +
        table(("Claim ID", "Caller-supplied claim", "Type", "Status", "Reference links"), claim_rows) +
        '</div></section><section><h2>Perspectives</h2><div class="scroll">' +
        table(("ID", "Label", "Claims"), view_rows) +
        '</div><p>Unassigned claims: ' + escape(join(report["unassigned_claim_ids"])) +
        '</p><p>Unframed claims: ' + escape(join(report["unframed_claim_ids"])) +
        '</p></section><section><h2>Potential conflicts and scope differences</h2><div class="scroll">' +
        table(("Left", "Right", "Status", "Different scope", "Unknown scope"), comparison_rows) +
        '</div></section><section><h2>Unresolved uncertainties</h2><div class="scroll">' +
        table(("Category", "Issue", "Target", "Review action", "Status"), uncertainty_rows) +
        '</div></section><section><h2>References — incomplete and unverified</h2><div class="scroll">' +
        table(("Number", "Title", "Source URL", "Missing metadata", "Conflicting titles"), ref_rows) +
        '</div></section><details><summary>Complete structured report and provenance</summary><pre>' +
        complete + '</pre></details></body></html>'
    ).encode("utf-8")


def build_export(request: ExportRequest):
    if not request.export_consent:
        raise ValueError("Explicit export consent required")
    report = synthesize(request.synthesis)
    if report["report_sha256"] != request.report_sha256:
        raise ValueError("Stale synthesis report")
    if request.format == "json":
        data = (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        media = "application/json"
    else:
        data = render_html(report)
        media = "text/html"
    if len(data) > MAX_EXPORT:
        raise ValueError("Research export exceeds output limit")
    return data, media


def register(app):
    @app.post("/studio/api/research/export")
    async def research_export(request: Request):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=393216, timeout_seconds=10.0,
            too_large_detail="Research export too large",
            timeout_detail="Research export timed out", timeout_status=408,
        )
        try:
            payload = ExportRequest.model_validate_json(body)
            data, media = build_export(payload)
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid research export", headers=NO_STORE) from None
        return Response(data, media_type=media, headers={
            **NO_STORE,
            "Content-Disposition": f'attachment; filename="nexus-research-draft.{payload.format}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": CSP,
            "X-Nexus-Content-SHA256": hashlib.sha256(data).hexdigest(),
        })
