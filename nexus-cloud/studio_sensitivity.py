"""Explicit, bounded sensitivity scenarios for reviewed meta-analysis and Bayesian plans."""
from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

import studio_bayesian as bayes
import studio_meta_analysis as meta
from studio_connections import operator_auth
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}


class MetaSensitivity(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    method: Literal["leave_one_out"]
    baseline: meta.MetaPlan


class Prior(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    alpha: int = Field(ge=1, le=100)
    beta: int = Field(ge=1, le=100)


class BayesianSensitivity(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    method: Literal["prior_sensitivity"]
    baseline: bayes.BayesianPlan
    alternative_priors: list[Prior] = Field(min_length=1, max_length=8)


Plan = Annotated[MetaSensitivity | BayesianSensitivity, Field(discriminator="method")]


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    plan: Plan


class ApprovedSensitivity(ReviewRequest):
    review_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    consent: bool = False


def preview(plan: Plan):
    if isinstance(plan, MetaSensitivity):
        baseline = meta.preview(plan.baseline)
        if len(plan.baseline.studies) < 3:
            raise ValueError("At least three studies are needed for leave-one-out pooling")
        scenarios = [{"excluded_study_id": s.study_id} for s in plan.baseline.studies]
    else:
        baseline = bayes.preview(plan.baseline)
        pairs = [(p.alpha, p.beta) for p in plan.alternative_priors]
        if len(set(pairs)) != len(pairs) or (
            plan.baseline.prior_alpha, plan.baseline.prior_beta
        ) in pairs:
            raise ValueError("Duplicate or baseline prior")
        scenarios = [p.model_dump() for p in plan.alternative_priors]
    canonical = json.dumps(plan.model_dump(), ensure_ascii=True, sort_keys=True,
                           separators=(",", ":"), allow_nan=False).encode("ascii")
    return {
        "schema_version": 1,
        "review_sha256": hashlib.sha256(b"nexus-sensitivity-v1\x00" + canonical).hexdigest(),
        "baseline_review_sha256": baseline["review_sha256"],
        "method": plan.method,
        "status": "review_only",
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
        "inference_eligible": baseline["inference_eligible"],
        "assumptions_verified": False,
        "execution_authorized": False,
    }


def meta_result(plan):
    return meta.run(meta.ApprovedMeta(
        plan=plan, consent=True, review_sha256=meta.preview(plan)["review_sha256"]))


def bayes_result(plan):
    return bayes.run(bayes.ApprovedBayesian(
        plan=plan, consent=True, review_sha256=bayes.preview(plan)["review_sha256"]))


def meta_summary(result):
    return {
        "common_effect": {k: v for k, v in result["common_effect"].items() if k != "weights"},
        "random_effects": {k: v for k, v in result["random_effects"].items() if k != "weights"},
        "heterogeneity": result["heterogeneity"],
        "diagnostics": result["diagnostics"],
    }


def range_of(values):
    return {"minimum": min(values), "maximum": max(values)}


def run(approved: ApprovedSensitivity):
    plan = approved.plan
    checked = preview(plan)
    if approved.consent is not True or checked["review_sha256"] != approved.review_sha256:
        raise ValueError("Changed or unapproved sensitivity plan")
    result = {
        **checked, "status": "computed", "inference_status": "assumptions_not_reported",
        "baseline": None, "scenario_results": [], "observed_ranges": None,
        "limitations": [
            "Sensitivity is conditional on the supplied data, scenarios and reported assumptions.",
            "The ranges describe only the scenarios tested; they are not confidence or credible intervals.",
            "No scenario is selected as the correct or preferred result.",
            "This does not validate assumptions, remove bias, establish causality or prove robustness.",
        ],
        "robustness_verified": False, "independent_verification": False,
        "causal_inference": False,
    }
    if not checked["inference_eligible"]:
        return result
    rows = result["scenario_results"]
    if isinstance(plan, MetaSensitivity):
        base = meta_summary(meta_result(plan.baseline))
        for excluded in plan.baseline.studies:
            subset = plan.baseline.model_copy(update={
                "studies": [s for s in plan.baseline.studies if s.study_id != excluded.study_id]})
            summary = meta_summary(meta_result(subset))
            rows.append({
                "excluded_study_id": excluded.study_id,
                "remaining_studies": len(subset.studies), **summary,
                "common_effect_change": summary["common_effect"]["effect"] - base["common_effect"]["effect"],
                "random_effect_change": summary["random_effects"]["effect"] - base["random_effects"]["effect"],
            })
        result["observed_ranges"] = {
            key: range_of([base[key]["effect"]] + [row[key]["effect"] for row in rows])
            for key in ("common_effect", "random_effects")
        }
        result["limitations"].append(
            "Leave-one-out pooling repeats the same methods and does not assess combinations of exclusions or publication bias.")
    else:
        base = bayes_result(plan.baseline)["posterior"]
        for prior in plan.alternative_priors:
            alternative = plan.baseline.model_copy(update={
                "prior_alpha": prior.alpha, "prior_beta": prior.beta})
            posterior = bayes_result(alternative)["posterior"]
            rows.append({
                "prior": prior.model_dump(), "posterior": posterior,
                "posterior_mean_change": posterior["mean"] - base["mean"],
                "threshold_probability_change": posterior["probability_above_threshold"] - base["probability_above_threshold"],
            })
        result["observed_ranges"] = {
            key: range_of([base[key]] + [row["posterior"][key] for row in rows])
            for key in ("mean", "probability_above_threshold")
        }
        result["limitations"].append(
            "Only the listed integer Beta priors vary; the likelihood and observations are held fixed.")
    result["baseline"] = base
    result["inference_status"] = "computed_conditional_on_reported_assumptions"
    return result


def register(app):
    async def parse(request, schema, function):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=65536, timeout_seconds=10.0,
            too_large_detail="Sensitivity request too large",
            timeout_detail="Sensitivity request timed out", timeout_status=408,
        )
        try:
            result = function(schema.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid sensitivity request", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)

    @app.post("/studio/api/statistics/sensitivity/review")
    async def review_endpoint(request: Request):
        return await parse(request, ReviewRequest, lambda data: preview(data.plan))

    @app.post("/studio/api/statistics/sensitivity/run")
    async def run_endpoint(request: Request):
        return await parse(request, ApprovedSensitivity, run)
