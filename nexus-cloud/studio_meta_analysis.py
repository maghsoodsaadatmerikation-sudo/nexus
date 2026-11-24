"""Bounded inverse-variance meta-analysis of caller-supplied study estimates."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Literal

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_connections import operator_auth
from studio_statistics import Z
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}


class Study(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    study_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,31}$")
    effect: float = Field(ge=-1e6, le=1e6)
    standard_error: float = Field(ge=1e-6, le=1e6)


class MetaPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    studies: list[Study] = Field(min_length=2, max_length=100)
    effect_scale: Literal["mean_difference", "standardized_mean_difference",
                          "log_odds_ratio", "log_risk_ratio"]
    confidence: Literal[90, 95, 99] = 95
    independent_estimates_reported: bool = False
    comparable_estimands_reported: bool = False
    valid_standard_errors_reported: bool = False


class ApprovedMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    plan: MetaPlan
    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    consent: bool = False


def preview(plan: MetaPlan):
    if len({study.study_id for study in plan.studies}) != len(plan.studies):
        raise ValueError("Duplicate study identifier")
    canonical = json.dumps(plan.model_dump(), ensure_ascii=True, sort_keys=True,
                           separators=(",", ":"), allow_nan=False).encode("ascii")
    return {
        "schema_version": 1,
        "review_sha256": hashlib.sha256(b"nexus-meta-analysis-v1\x00" + canonical).hexdigest(),
        "status": "review_only", "study_count": len(plan.studies),
        "effect_scale": plan.effect_scale, "confidence_percent": plan.confidence,
        "methods": ["common_effect_inverse_variance", "random_effects_der_simonian_laird"],
        "inference_eligible": (plan.independent_estimates_reported
                               and plan.comparable_estimands_reported
                               and plan.valid_standard_errors_reported),
        "assumptions_verified": False, "execution_authorized": False,
    }


def weighted_mean(effects, weights):
    total = math.fsum(weights)
    # Anchor at a supplied estimate to avoid needless loss of precision.
    anchor = effects[0]
    center = anchor + math.fsum(w*(e-anchor) for e, w in zip(effects, weights))/total
    return center, total


def pooled(effects, weights, studies, confidence):
    center, total = weighted_mean(effects, weights)
    se = math.sqrt(1/total)
    half = Z[confidence]*se
    return {
        "effect": center, "standard_error": se,
        "confidence_interval": {"lower": center-half, "upper": center+half,
                                "confidence_percent": confidence,
                                "method": "normal_approximation"},
        "weights": [{"study_id": s.study_id, "fraction": w/total}
                    for s, w in zip(studies, weights)],
    }


def run(approved: ApprovedMeta):
    plan = approved.plan
    checked = preview(plan)
    if approved.consent is not True or checked["review_sha256"] != approved.review_sha256:
        raise ValueError("Changed or unapproved meta-analysis")
    result = {
        **checked, "status": "computed", "inference_status": "assumptions_not_reported",
        "common_effect": None, "random_effects": None, "heterogeneity": None,
        "diagnostics": [],
        "limitations": [
            "Effect estimates and standard errors are supplied by the caller; source data and study independence are not verified.",
            "Both models require comparable effect scales, directions and estimands.",
            "Random-effects variance uses DerSimonian–Laird, which may be unstable with few studies.",
            "Normal-approximation intervals ignore uncertainty in estimated heterogeneity and may be too narrow.",
            "I-squared and Q are descriptive heterogeneity measures, not tests of clinical comparability.",
            "No publication-bias assessment, risk-of-bias weighting, causal inference or clinical recommendation.",
        ],
        "independent_verification": False, "causal_inference": False,
        "prediction_validated": False,
    }
    if not checked["inference_eligible"]:
        return result
    effects = [s.effect for s in plan.studies]
    variances = [s.standard_error**2 for s in plan.studies]
    weights = [1/v for v in variances]
    center, total = weighted_mean(effects, weights)
    q = math.fsum(w*(e-center)**2 for e, w in zip(effects, weights))
    df = len(effects)-1
    # C = sum(w) - sum(w^2)/sum(w), evaluated without cancellation
    # for very unequal weights. Pair products are positive and bounded.
    c = 2*math.fsum(weights[i]*weights[j] for i in range(len(weights))
                    for j in range(i+1, len(weights)))/total
    tau2 = max(0.0, (q-df)/c)
    random_weights = [1/(v+tau2) for v in variances]
    result["common_effect"] = pooled(effects, weights, plan.studies, plan.confidence)
    result["random_effects"] = pooled(effects, random_weights, plan.studies, plan.confidence)
    result["heterogeneity"] = {
        "cochran_q": q, "degrees_of_freedom": df,
        "i_squared_percent": max(0.0, (q-df)/q)*100 if q else 0.0,
        "tau_squared": tau2, "tau_squared_method": "der_simonian_laird",
    }
    if len(effects) < 10:
        result["diagnostics"].append("few_studies_heterogeneity_and_intervals_uncertain")
    if tau2 == 0:
        result["diagnostics"].append("zero_estimated_heterogeneity_not_proof_of_homogeneity")
    if max(weights)/total > 0.9:
        result["diagnostics"].append("common_effect_dominated_by_one_study")
    result["inference_status"] = "computed_conditional_on_reported_assumptions"
    return result


def register(app):
    async def parse(request, schema, function):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=65536, timeout_seconds=10.0,
            too_large_detail="Meta-analysis request too large",
            timeout_detail="Meta-analysis request timed out", timeout_status=408,
        )
        try:
            result = function(schema.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid meta-analysis request", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)

    @app.post("/studio/api/statistics/meta-analysis/review")
    async def review_endpoint(request: Request):
        return await parse(request, MetaPlan, preview)

    @app.post("/studio/api/statistics/meta-analysis/run")
    async def run_endpoint(request: Request):
        return await parse(request, ApprovedMeta, run)
