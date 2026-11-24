"""Versioned report layouts for audited metrics; no invented domain conclusions."""
from __future__ import annotations

from html import escape

TEMPLATES = {
    "research-v1": {
        "title": "Research analysis report",
        "sections": ("Scope and method", "Observed results", "Input provenance", "Limitations and review"),
        "scope": "Deterministic descriptive analysis of the supplied inputs. No sampling or inferential model was applied.",
        "limits": "Assess study design, sample selection, units, uncertainty and source reliability separately.",
    },
    "business-v1": {
        "title": "Business analysis brief",
        "sections": ("Analysis scope", "Metric summary", "Calculation trace", "Decision review"),
        "scope": "Descriptive metrics from supplied inputs; no targets, forecasts or financial recommendations inferred.",
        "limits": "Confirm metric definitions, currency, time period and business context before making decisions.",
    },
    "technical-v1": {
        "title": "Technical verification report",
        "sections": ("Verification method", "Computed outputs", "Dependency trace", "Verification boundaries"),
        "scope": "Recomputed supported operations were checked for consistency against the supplied analysis plan.",
        "limits": "Consistency is not independent validation of source inputs, security, deployment or system correctness.",
    },
}

NOTICE = "Computational consistency only; supplied inputs are not independently verified. Human review is required."


def catalog():
    return [{"id": key, "title": value["title"], "sections": list(value["sections"])}
            for key, value in TEMPLATES.items()]


def render_template(result, template_id):
    if template_id not in TEMPLATES:
        raise ValueError("Unknown report template")
    spec = TEMPLATES[template_id]

    def text(value):
        return escape(str(value), quote=True)

    def table(headers, rows):
        headings = "".join(f'<th scope="col">{text(h)}</th>' for h in headers)
        cells = "".join("<tr>" + "".join(f"<td>{text(v)}</td>" for v in row) + "</tr>"
                        for row in rows)
        return f"<table><thead><tr>{headings}</tr></thead><tbody>{cells}</tbody></table>"

    metrics = []
    provenance = []
    for step in result["results"]:
        for metric, value in step["metrics"].items():
            metrics.append((step["step_id"], step["operation"], metric, value))
        for ref in step.get("input_provenance", []):
            provenance.append((step["step_id"], ref["step_id"], ref["metric"], ref["value"]))
    blocks = [
        f'<p>{text(spec["scope"])}</p><p>Review SHA-256: <code>{text(result["review_sha256"])}</code></p>',
        table(("Step", "Operation", "Metric", "Value"), metrics),
        table(("Step", "Source step", "Source metric", "Value"), provenance)
        if provenance else "<p>No inter-step metric references.</p>",
        f'<p>{text(NOTICE)}</p><p>{text(spec["limits"])}</p>',
    ]
    sections = "".join(f"<section><h2>{text(heading)}</h2>{body}</section>"
                       for heading, body in zip(spec["sections"], blocks))
    policy = "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta http-equiv="Content-Security-Policy" content="{policy}">'
        f'<title>{text(spec["title"])}</title><style>'
        'body{margin:0;background:#f5f7fa;color:#172538;font:16px system-ui,sans-serif}'
        'main{max-width:1000px;margin:auto;padding:24px}section{background:white;'
        'padding:20px;margin:16px 0;border:1px solid #cbd5e1;border-radius:8px}'
        'h1,h2{margin-top:0}code{overflow-wrap:anywhere}table{width:100%;'
        'border-collapse:collapse;overflow-wrap:anywhere}td,th{text-align:left;'
        'padding:8px;border-bottom:1px solid #cbd5e1}th{background:#eef2f6}'
        '@media print{body{background:white}main{padding:0}tr{break-inside:avoid}}'
        '</style></head><body><main>'
        f'<h1>NEXUS | {text(spec["title"])}</h1><p>Template: {text(template_id)}</p>'
        + sections + "</main></body></html>"
    ).encode("utf-8")
