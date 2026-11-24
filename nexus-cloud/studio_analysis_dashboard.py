"""Self-contained HTML dashboard with native, script-free disclosure controls."""
from __future__ import annotations

from html import escape

from studio_analysis_chart import CHART_METRICS, chart_svg


def dashboard(result, metrics):
    if not 1 <= len(metrics) <= 4 or len(set(metrics)) != len(metrics):
        raise ValueError("Select one to four distinct metrics")
    if any(metric not in CHART_METRICS for metric in metrics):
        raise ValueError("Unsupported dashboard metric")
    sections = []
    for metric in metrics:
        # No implicit unit conversions or substitutions. The selected metric
        # must have at least one observation; chart_svg checks numeric bounds.
        chart = chart_svg(result, metric).decode("utf-8")
        rows = []
        missing = []
        for row in result["results"]:
            step = escape(row["step_id"])
            if metric not in row["metrics"]:
                missing.append(step)
                continue
            value = escape(str(row["metrics"][metric]))
            operation = escape(row["operation"])
            rows.append(f"<tr><th scope='row'>{step}</th><td>{operation}</td><td>{value}</td></tr>")
        omitted = ("<p>Not applicable: " + ", ".join(missing) + ".</p>") if missing else ""
        sections.append(
            f'<details open><summary>{escape(metric)}</summary>'
            f'<figure>{chart}<figcaption>Zero-based scale; this panel has its own scale.</figcaption></figure>'
            '<table><thead><tr><th scope="col">Step</th><th scope="col">Operation</th>'
            '<th scope="col">Value</th></tr></thead><tbody>' + "".join(rows)
            + "</tbody></table>" + omitted + "</details>"
        )
    digest = escape(result["review_sha256"])
    # Fixed stylesheet only. No scripts, external URLs, or raw source prose.
    policy = "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta http-equiv="Content-Security-Policy" content="{policy}">'
        '<title>NEXUS analysis dashboard</title><style>'
        'body{font:16px system-ui,sans-serif;color:#172538;background:#f4f6f9;margin:0}'
        'main{max-width:1000px;margin:auto;padding:24px}h1{margin:0 0 12px}'
        'code{overflow-wrap:anywhere}details{background:white;border:1px solid #cbd5e1;'
        'border-radius:10px;margin:18px 0;padding:16px}summary{font-size:19px;'
        'font-weight:600;cursor:pointer}figure{margin:16px 0}svg{width:100%;height:auto}'
        'figcaption{font-size:14px;color:#475569}table{border-collapse:collapse;width:100%;'
        'overflow-wrap:anywhere}td,th{text-align:left;padding:8px;border-bottom:1px solid #cbd5e1}'
        '@media print{body{background:white}main{padding:0}details{break-inside:avoid}}'
        '</style></head><body><main><h1>NEXUS | Analysis dashboard</h1>'
        '<p>Computational consistency only; supplied inputs. Check that compared values have compatible units. '
        'Panels use independent scales. Open or close panels using their headings.</p>'
        f'<p>Review SHA-256: <code>{digest}</code></p>'
        + "".join(sections) + '</main></body></html>'
    ).encode("utf-8")
