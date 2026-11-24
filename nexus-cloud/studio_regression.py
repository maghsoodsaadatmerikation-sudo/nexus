"""Deterministic simple linear regression and rank correlation for bounded data."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Literal

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_analysis_batch import BoundedInteger
from studio_connections import operator_auth
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    x: BoundedInteger
    y: BoundedInteger


class RegressionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    observations: list[Observation] = Field(min_length=3, max_length=1000)
    method: Literal["simple_linear_with_intercept"] = "simple_linear_with_intercept"


class ApprovedRegression(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    plan: RegressionPlan
    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    consent: bool = False


def preview(plan: RegressionPlan):
    canonical = json.dumps(plan.model_dump(), sort_keys=True, ensure_ascii=True,
                           separators=(",", ":")).encode("ascii")
    return {
        "schema_version": 1,
        "review_sha256": hashlib.sha256(b"nexus-regression-v1\x00" + canonical).hexdigest(),
        "status": "review_only",
        "count": len(plan.observations),
        "method": plan.method,
        "predictor": "x",
        "outcome": "y",
        "inference_planned": False,
        "execution_authorized": False,
    }


def centered_sums(x, y):
    # Integer numerators of the centered sums, multiplied by n.
    # Avoid catastrophic cancellation in floating-point raw-moment formulas.
    n = len(x)
    sx, sy = sum(x), sum(y)
    return (n * sum(v*v for v in x) - sx*sx,
            n * sum(v*v for v in y) - sy*sy,
            n * sum(a*b for a, b in zip(x, y)) - sx*sy)


def doubled_ranks(values):
    """Average ranks for ties, scaled by two to stay exact integers."""
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0] * len(values)
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and values[order[j]] == values[order[i]]:
            j += 1
        for k in range(i, j):
            ranks[order[k]] = i + 1 + j
        i = j
    return ranks


def correlation(a, b, c):
    if a == 0 or b == 0:
        return None
    return max(-1.0, min(1.0, c / math.sqrt(a*b)))


def run(approved: ApprovedRegression):
    reviewed = preview(approved.plan)
    if not approved.consent or approved.review_sha256 != reviewed["review_sha256"]:
        raise ValueError("Changed or unapproved regression")
    x = [row.x for row in approved.plan.observations]
    y = [row.y for row in approved.plan.observations]
    n = len(x)
    a, b, c = centered_sums(x, y)
    pearson = correlation(a, b, c)
    spearman = correlation(*centered_sums(doubled_ranks(x), doubled_ranks(y)))
    fit = None
    diagnostics = []
    if a == 0:
        diagnostics.append("constant_predictor_no_unique_slope")
    else:
        # SSE = (a*b - c*c)/(n*a). Exact integer subtraction keeps
        # perfectly fitted or almost perfectly fitted observations stable.
        sse_numerator = a*b - c*c
        sse = sse_numerator / (n*a)
        fit = {
            "slope": c/a,
            "intercept": (sum(y)*a - c*sum(x))/(n*a),
            "centered_x": sum(x)/n,
            "centered_y": sum(y)/n,
            "r_squared": c*c/(a*b) if b else None,
            "standardized_slope": pearson,
            "residual_sum_of_squares": sse,
            "training_rmse": math.sqrt(sse/n),
            "residual_standard_error": math.sqrt(sse/(n-2)),
        }
        if sse_numerator == 0:
            diagnostics.append("perfect_in_sample_fit_not_external_validation")
    if b == 0:
        diagnostics.append("constant_outcome_correlation_and_r_squared_undefined")
    if len(set(x)) < n:
        diagnostics.append("predictor_ties_present")
    if len(set(y)) < n:
        diagnostics.append("outcome_ties_present")
    return {
        **reviewed,
        "status": "computed",
        "correlations": {"pearson_r": pearson, "spearman_rho_average_ties": spearman},
        "fit": fit,
        "diagnostics": diagnostics,
        "limitations": [
            "This is descriptive ordinary least squares on supplied observations, not a causal estimate.",
            "Pearson measures linear association; Spearman measures rank association with average ties.",
            "The standardized simple-regression slope equals Pearson r when both variables vary.",
            "Training fit and residual error do not estimate out-of-sample prediction accuracy.",
            "Independence, linearity, missingness, heteroscedasticity, confounding and representativeness are not verified.",
            "No p-values, confidence intervals, extrapolation or automatic model selection are produced.",
        ],
        "assumptions_verified": False,
        "causal_inference": False,
        "prediction_validated": False,
        "independent_verification": False,
    }


def register(app):
    async def parse(request, schema, function):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=131072, timeout_seconds=10.0,
            too_large_detail="Regression request too large",
            timeout_detail="Regression request timed out", timeout_status=408,
        )
        try:
            result = function(schema.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid regression request", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)

    @app.post("/studio/api/statistics/regression/review")
    async def review_endpoint(request: Request):
        return await parse(request, RegressionPlan, preview)

    @app.post("/studio/api/statistics/regression/run")
    async def run_endpoint(request: Request):
        return await parse(request, ApprovedRegression, run)
