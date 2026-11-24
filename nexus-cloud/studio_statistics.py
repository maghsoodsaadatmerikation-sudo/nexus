"""Bounded paired-sample descriptive statistics and exact sign test."""
from __future__ import annotations

import hashlib
import json
import math
from statistics import mean, median, stdev
from typing import Literal

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_analysis_batch import BoundedInteger
from studio_connections import operator_auth
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}
Z = {90: 1.6448536269514722, 95: 1.959963984540054, 99: 2.5758293035489004}


class Pair(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    before: BoundedInteger
    after: BoundedInteger


class PairedPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    pairs: list[Pair] = Field(min_length=2, max_length=1000)
    confidence: Literal[90, 95, 99] = 95
    independent_pairs_reported: bool = False
    pairing_valid_reported: bool = False


class ApprovedPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    plan: PairedPlan
    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    consent: bool = False


def preview(plan: PairedPlan):
    canonical = json.dumps(plan.model_dump(), sort_keys=True, ensure_ascii=True,
                           separators=(",", ":")).encode("ascii")
    return {
        "schema_version": 1,
        "review_sha256": hashlib.sha256(b"nexus-paired-sign-v1\x00" + canonical).hexdigest(),
        "status": "review_only",
        "pair_count": len(plan.pairs),
        "direction": "after_minus_before",
        "method": "two_sided_exact_sign_test_conditional_on_nonzero_differences",
        "confidence": plan.confidence,
        "inference_eligible": plan.independent_pairs_reported and plan.pairing_valid_reported,
        "assumptions_verified": False,
        "execution_authorized": False,
    }


def wilson(k: int, n: int, confidence: int):
    p = k / n
    z = Z[confidence]
    denominator = 1 + z*z/n
    center = (p + z*z/(2*n)) / denominator
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / denominator
    return {"lower": max(0.0, center-half), "upper": min(1.0, center+half),
            "confidence_percent": confidence, "method": "wilson_score_approximate"}


def run(approved: ApprovedPlan):
    reviewed = preview(approved.plan)
    if approved.consent is not True or approved.review_sha256 != reviewed["review_sha256"]:
        raise ValueError("Changed or unapproved analysis")
    differences = [pair.after - pair.before for pair in approved.plan.pairs]
    positive = sum(d > 0 for d in differences)
    negative = sum(d < 0 for d in differences)
    n = positive + negative
    ties = len(differences) - n
    result = {
        **reviewed,
        "status": "computed",
        "descriptive": {
            "count": len(differences), "mean_change": mean(differences),
            "median_change": median(differences), "sample_sd_change": stdev(differences),
            "minimum_change": min(differences), "maximum_change": max(differences),
            "positive": positive, "negative": negative, "ties": ties,
            "positive_fraction_among_nonzero": positive / n if n else None,
        },
        "inference": None,
        "limitations": [
            "The sign test targets equal probabilities of positive and negative change among nonzero differences.",
            "Zero differences are excluded only from inference, not descriptive statistics.",
            "Pairing and independence are caller-reported, not verified. No adjustment for selection bias or multiple testing.",
            "The Wilson interval is approximate and concerns the positive fraction among nonzero differences, not the mean change.",
            "No causal, clinical or practical significance is inferred.",
        ],
        "causal_inference": False,
        "independent_verification": False,
    }
    if not reviewed["inference_eligible"]:
        result["inference_status"] = "assumptions_not_reported"
    elif not n:
        result["inference_status"] = "all_differences_zero"
    else:
        # Exact integer binomial tail; avoids underflow in individual terms
        # and avoids a numerical integration dependency.
        lower = sum(math.comb(n, j) for j in range(min(positive, negative)+1))
        p_value = min(1.0, (2 * lower) / (1 << n))
        result["inference"] = {
            "nonzero_pairs": n, "null_positive_probability": 0.5,
            "two_sided_p_value": p_value,
            "positive_fraction_interval": wilson(positive, n, approved.plan.confidence),
        }
        result["inference_status"] = "computed_conditional_on_reported_assumptions"
    return result


def register(app):
    async def parse(request, schema, function):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=131072, timeout_seconds=10.0,
            too_large_detail="Paired analysis too large",
            timeout_detail="Paired analysis timed out", timeout_status=408,
        )
        try:
            result = function(schema.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid paired analysis", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)

    @app.post("/studio/api/statistics/paired/review")
    async def review_endpoint(request: Request):
        return await parse(request, PairedPlan, preview)

    @app.post("/studio/api/statistics/paired/run")
    async def run_endpoint(request: Request):
        return await parse(request, ApprovedPlan, run)
