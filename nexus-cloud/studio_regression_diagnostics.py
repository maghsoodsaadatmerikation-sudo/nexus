"""Review-bound influence diagnostics for simple OLS; never delete observations."""
from __future__ import annotations

import hashlib
import json
import math

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

import studio_regression as regression
from studio_connections import operator_auth
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}


class DiagnosticPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    regression: regression.RegressionPlan


class ApprovedDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    plan: DiagnosticPlan
    review_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    consent: bool = False


def preview(plan: DiagnosticPlan):
    baseline = regression.preview(plan.regression)
    n = baseline["count"]
    if n < 4:
        raise ValueError("Require at least four observations")
    canonical = json.dumps(plan.model_dump(), sort_keys=True, ensure_ascii=True,
                           separators=(",", ":")).encode("ascii")
    return {
        "schema_version": 1,
        "review_sha256": hashlib.sha256(b"nexus-regression-diagnostics-v1\x00" + canonical).hexdigest(),
        "baseline_review_sha256": baseline["review_sha256"],
        "status": "review_only", "count": n,
        "heuristic_thresholds": {"leverage": 4/n, "absolute_internal_studentized_residual": 2,
                                 "cooks_distance": 4/n},
        "execution_authorized": False,
    }


def run(approved: ApprovedDiagnostics):
    checked = preview(approved.plan)
    if approved.consent is not True or approved.review_sha256 != checked["review_sha256"]:
        raise ValueError("Changed or unapproved diagnostic plan")
    plan = approved.plan.regression
    baseline = regression.run(regression.ApprovedRegression(
        plan=plan, consent=True, review_sha256=checked["baseline_review_sha256"]))
    result = {
        **checked, "status": "computed", "baseline": baseline,
        "diagnostic_status": "constant_predictor" if baseline["fit"] is None else "computed",
        "observations": [],
        "limitations": [
            "Flags are screening heuristics, not proof of errors, outliers or bias.",
            "Internal studentization uses full-model residual variance; it is not an external studentized test.",
            "Cook's distance describes influence on the fitted model, not scientific importance.",
            "Leave-one-out changes retain the same model specification and are not a validation of generalization.",
            "Selection, publication, measurement and confounding biases cannot be inferred from these diagnostics.",
        ],
        "bias_verified": False, "assumptions_verified": False,
        "automatic_exclusions": False, "independent_verification": False,
    }
    if baseline["fit"] is None:
        return result
    x = [row.x for row in plan.observations]
    y = [row.y for row in plan.observations]
    n, sx, sy = len(x), sum(x), sum(y)
    a, b, c = regression.centered_sums(x, y)
    sse_num = a*b - c*c
    mse = sse_num/(n*a*(n-2))
    if sse_num == 0:
        result["diagnostic_status"] = "zero_residual_variance"
    for i, (xi, yi) in enumerate(zip(x, y)):
        dx, dy = n*xi-sx, n*yi-sy
        # Exact rational residual and leverage, including an exact h=1 test.
        residual = (dy*a-c*dx)/(n*a)
        h_num, h_den = a+dx*dx, n*a
        leverage = h_num/h_den
        one_minus_h = (h_den-h_num)/h_den
        studentized = cooks = None
        flags = []
        if leverage > 4/n:
            flags.append("high_leverage")
        if h_num == h_den:
            flags.append("unit_leverage_diagnostics_undefined")
        elif sse_num:
            studentized = residual/math.sqrt(mse*one_minus_h)
            cooks = studentized**2*leverage/(2*one_minus_h)
            if abs(studentized) > 2:
                flags.append("large_internal_studentized_residual")
            if cooks > 4/n:
                flags.append("large_cooks_distance")
        # Recompute deleted-observation slope exactly from integer sums.
        # Unlike a floating-point subtraction of hat values, this remains
        # well-defined for nearly constant predictors and large offsets.
        m = n-1
        sx2, sy2 = sx-xi, sy-yi
        deleted_a = m*((a+sx*sx)//n-xi*xi)-sx2*sx2
        deleted_c = m*((c+sx*sy)//n-xi*yi)-sx2*sy2
        deleted_slope = deleted_c/deleted_a if deleted_a else None
        slope_change = ((deleted_c*a-c*deleted_a)/(deleted_a*a)
                        if deleted_a else None)
        if deleted_a == 0:
            flags.append("deleted_fit_has_constant_predictor")
        result["observations"].append({
            "observation_index": i, "residual": residual, "leverage": leverage,
            "internal_studentized_residual": studentized, "cooks_distance": cooks,
            "leave_one_out_slope": deleted_slope, "slope_change": slope_change,
            "flags": flags,
        })
    return result


def register(app):
    async def parse(request, schema, function):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=131072, timeout_seconds=10.0,
            too_large_detail="Diagnostic request too large",
            timeout_detail="Diagnostic request timed out", timeout_status=408)
        try:
            result = function(schema.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid diagnostic request", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)

    @app.post("/studio/api/statistics/diagnostics/review")
    async def review_endpoint(request: Request):
        return await parse(request, DiagnosticPlan, preview)

    @app.post("/studio/api/statistics/diagnostics/run")
    async def run_endpoint(request: Request):
        return await parse(request, ApprovedDiagnostics, run)
