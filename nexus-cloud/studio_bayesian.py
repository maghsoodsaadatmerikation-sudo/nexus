"""Bounded, consent-gated Beta-Bernoulli updating with explicit assumptions."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Literal

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_connections import operator_auth
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}


class BayesianPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    prior_alpha: int = Field(ge=1, le=100)
    prior_beta: int = Field(ge=1, le=100)
    successes: int = Field(ge=0, le=1000)
    failures: int = Field(ge=0, le=1000)
    credibility: Literal[90, 95, 99] = 95
    threshold_per_thousand: int = Field(default=500, ge=0, le=1000)
    independent_trials_reported: bool = False
    common_probability_reported: bool = False


class ApprovedBayesian(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    plan: BayesianPlan
    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    consent: bool = False


def preview(plan: BayesianPlan):
    n = plan.successes + plan.failures
    if not 1 <= n <= 1000:
        raise ValueError("Require 1–1000 observations in total")
    canonical = json.dumps(plan.model_dump(), ensure_ascii=True, sort_keys=True,
                           separators=(",", ":")).encode("ascii")
    return {
        "schema_version": 1,
        "review_sha256": hashlib.sha256(b"nexus-beta-bernoulli-v1\x00" + canonical).hexdigest(),
        "status": "review_only",
        "model": "beta_prior_bernoulli_likelihood",
        "observations": n,
        "prior": {"alpha": plan.prior_alpha, "beta": plan.prior_beta},
        "successes": plan.successes, "failures": plan.failures,
        "credibility_percent": plan.credibility,
        "threshold_per_thousand": plan.threshold_per_thousand,
        "inference_eligible": plan.independent_trials_reported and plan.common_probability_reported,
        "assumptions_verified": False,
        "execution_authorized": False,
    }


class IntegerBeta:
    """Integer-shape beta CDF via its binomial-tail identity.

    Evaluate tails directly in log space, not by subtracting from one.
    Quantiles use bounded bisection. Outputs are floating-point approximations.
    """
    def __init__(self, alpha: int, beta: int):
        self.alpha = alpha
        self.n = alpha + beta - 1
        base = math.lgamma(self.n + 1)
        self.log_coefficients = [
            base - math.lgamma(j + 1) - math.lgamma(self.n - j + 1)
            for j in range(self.n + 1)
        ]

    def tail(self, p: float, *, upper: bool = False) -> float:
        if p <= 0:
            return 1.0 if upper else 0.0
        if p >= 1:
            return 0.0 if upper else 1.0
        lp, lq = math.log(p), math.log1p(-p)
        indices = range(self.alpha) if upper else range(self.alpha, self.n + 1)
        total = math.fsum(math.exp(self.log_coefficients[j] + j*lp + (self.n-j)*lq)
                          for j in indices)
        return min(1.0, max(0.0, total))

    def quantile(self, q: float) -> float:
        low, high = 0.0, 1.0
        for _ in range(53):
            middle = (low + high) / 2
            if self.tail(middle) < q:
                low = middle
            else:
                high = middle
        return (low + high) / 2


def run(approved: ApprovedBayesian):
    plan = approved.plan
    reviewed = preview(plan)
    if approved.consent is not True or approved.review_sha256 != reviewed["review_sha256"]:
        raise ValueError("Changed or unapproved Bayesian analysis")
    result = {
        **reviewed,
        "status": "computed",
        "observed_success_fraction": plan.successes / reviewed["observations"],
        "posterior": None,
        "inference_status": "assumptions_not_reported",
        "limitations": [
            "The likelihood assumes independent binary trials sharing one fixed success probability.",
            "The prior is explicitly supplied; its suitability and the data-generating process are not verified.",
            "Credible intervals are conditional posterior probabilities, not frequentist confidence intervals.",
            "Quantiles and tail probabilities are numerical approximations; extremely small tails may underflow to zero.",
            "The predictive probability concerns a single new trial under the same model, not validated prediction.",
            "No causal, clinical, decision or general-purpose truth conclusion is inferred.",
        ],
        "causal_inference": False,
        "prediction_validated": False,
        "independent_verification": False,
    }
    if not reviewed["inference_eligible"]:
        return result
    a, b = plan.prior_alpha + plan.successes, plan.prior_beta + plan.failures
    distribution = IntegerBeta(a, b)
    q = (1 - plan.credibility/100) / 2
    posterior_mean = a / (a+b)
    threshold = plan.threshold_per_thousand / 1000
    result["posterior"] = {
        "alpha": a, "beta": b,
        "mean": posterior_mean,
        "variance": a*b / ((a+b)**2 * (a+b+1)),
        "prior_mean": plan.prior_alpha / (plan.prior_alpha + plan.prior_beta),
        "credible_interval": {
            "method": "equal_tailed_beta_quantiles",
            "credibility_percent": plan.credibility,
            "lower": distribution.quantile(q),
            "upper": distribution.quantile(1-q),
        },
        "probability_above_threshold": distribution.tail(threshold, upper=True),
        "next_trial_success_probability_under_model": posterior_mean,
    }
    result["inference_status"] = "computed_conditional_on_reported_assumptions"
    return result


def register(app):
    async def parse(request, schema, function):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=8192, timeout_seconds=10.0,
            too_large_detail="Bayesian request too large",
            timeout_detail="Bayesian request timed out", timeout_status=408,
        )
        try:
            result = function(schema.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid Bayesian request", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)

    @app.post("/studio/api/statistics/bayesian/review")
    async def review_endpoint(request: Request):
        return await parse(request, BayesianPlan, preview)

    @app.post("/studio/api/statistics/bayesian/run")
    async def run_endpoint(request: Request):
        return await parse(request, ApprovedBayesian, run)
