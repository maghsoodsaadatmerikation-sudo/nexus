"""Static signed bar charts for explicitly selected analysis metrics."""
from __future__ import annotations

from html import escape
from math import isfinite

TEXT_METRICS = frozenset({"characters", "utf8_bytes", "whitespace_tokens", "lines"})
NUMBER_METRICS = frozenset({"count", "sum", "min", "max", "mean", "median"})
CHART_METRICS = TEXT_METRICS | NUMBER_METRICS


def chart_svg(result, metric):
    if metric not in CHART_METRICS:
        raise ValueError("Unsupported chart metric")
    # One metric only. Never mix unrelated units or silently substitute values.
    rows = [(row["step_id"], row["metrics"][metric])
            for row in result["results"] if metric in row["metrics"]]
    if not rows or len(rows) > 4:
        raise ValueError("No supported values for selected metric")
    if any(type(value) not in (int, float) or not isfinite(value)
           for _, value in rows):
        raise ValueError("Invalid chart value")
    values = [value for _, value in rows]
    lo, hi = min(0, min(values)), max(0, max(values))
    if lo == hi:
        hi = 1
    left, right = 260, 900

    def pos(value):
        return left + (right - left) * (value - lo) / (hi - lo)

    def label(x, y, content, size=16, color="#172538", anchor="start"):
        return (f'<text x="{x}" y="{y}" font-family="sans-serif" font-size="{size}" '
                f'fill="{color}" text-anchor="{anchor}">{escape(str(content))}</text>')

    height = 190 + len(rows) * 66
    baseline = pos(0)
    body = [f'<rect width="960" height="{height}" fill="#ffffff"/>',
            label(28, 36, "NEXUS | Analysis chart", 24),
            label(28, 62, "Metric: " + metric + " — compare only like units", 15),
            label(28, 85, "Computational consistency only; supplied inputs", 13),
            label(28, 106, "Review SHA-256: " + result["review_sha256"], 11),
            f'<line x1="{baseline:.3f}" x2="{baseline:.3f}" y1="123" y2="{height-43}" '
            'stroke="#64748b" stroke-width="1"/>']
    for index, (step_id, value) in enumerate(rows):
        y = 135 + 66 * index
        x = pos(value)
        body.append(label(28, y + 16, step_id, 12))
        body.append(f'<rect x="{min(x, baseline):.3f}" y="{y}" '
                    f'width="{abs(x-baseline):.3f}" height="19" '
                    f'fill="{"#16856c" if value >= 0 else "#9b4545"}"/>')
        # Separate value row preserves exact Python numeric representation,
        # including zero or values whose bar is subpixel at this scale.
        body.append(label(28, y + 38, str(value), 13))
    body.append(label(left, height - 15, str(lo), 12, anchor="start"))
    body.append(label(right, height - 15, str(hi), 12, anchor="end"))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="960" height="{height}" '
            f'viewBox="0 0 960 {height}" role="img">'
            f'<title>{escape(metric)} by analysis step</title>'
            '<desc>Signed horizontal bars with a zero baseline and exact value labels. '
            'Only steps providing the selected metric are included.</desc>'
            + "".join(body) + "</svg>").encode("utf-8")
