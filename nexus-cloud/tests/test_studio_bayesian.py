import math

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_bayesian import ApprovedBayesian, BayesianPlan, IntegerBeta, preview, run, register


def approved(**overrides):
    plan = BayesianPlan.model_validate({
        "prior_alpha": 1, "prior_beta": 1, "successes": 1, "failures": 0,
        "independent_trials_reported": True, "common_probability_reported": True,
        **overrides,
    })
    return ApprovedBayesian(plan=plan, review_sha256=preview(plan)["review_sha256"], consent=True)


def test_analytic_beta_two_one():
    data = approved()
    result = run(data)
    assert result == run(data)
    p = result["posterior"]
    assert (p["alpha"], p["beta"]) == (2, 1)
    assert p["mean"] == pytest.approx(2/3)
    assert p["variance"] == pytest.approx(1/18)
    assert p["credible_interval"]["lower"] == pytest.approx(math.sqrt(0.025))
    assert p["credible_interval"]["upper"] == pytest.approx(math.sqrt(0.975))
    assert p["probability_above_threshold"] == pytest.approx(0.75)
    assert p["next_trial_success_probability_under_model"] == p["mean"]
    assert not result["causal_inference"] and not result["prediction_validated"]


def test_symmetric_posterior_and_boundary_thresholds():
    p = run(approved(successes=5, failures=5, credibility=99))["posterior"]
    assert p["mean"] == 0.5
    assert p["probability_above_threshold"] == pytest.approx(0.5)
    ci = p["credible_interval"]
    assert ci["lower"] + ci["upper"] == pytest.approx(1)
    assert run(approved(threshold_per_thousand=0))["posterior"]["probability_above_threshold"] == 1
    assert run(approved(threshold_per_thousand=1000))["posterior"]["probability_above_threshold"] == 0


def test_large_and_skewed_posterior():
    p = run(approved(prior_alpha=100, prior_beta=100, successes=1000))["posterior"]
    assert p["mean"] == pytest.approx(1100/1200)
    assert 0 < p["credible_interval"]["lower"] < p["mean"] < p["credible_interval"]["upper"] < 1
    for a, b in [(1, 1001), (1001, 1), (600, 600)]:
        dist = IntegerBeta(a, b)
        for q in (0.005, 0.025, 0.975, 0.995):
            assert dist.tail(dist.quantile(q)) == pytest.approx(q, abs=1e-10)
        assert dist.tail(0.5) + dist.tail(0.5, upper=True) == pytest.approx(1, abs=1e-10)


def test_assumptions_consent_and_stale_plan():
    result = run(approved(common_probability_reported=False))
    assert result["posterior"] is None and not result["assumptions_verified"]
    data = approved()
    with pytest.raises(ValueError):
        run(data.model_copy(update={"consent": False}))
    with pytest.raises(ValueError):
        run(data.model_copy(update={"plan": approved(failures=2).plan}))


@pytest.mark.parametrize("bad", [
    {"prior_alpha": 0}, {"prior_beta": True}, {"successes": 1.5},
    {"successes": 1000, "failures": 1}, {"successes": 0, "failures": 0},
    {"threshold_per_thousand": 1001}, {"credibility": 92},
])
def test_invalid_plan(bad):
    with pytest.raises(ValueError):
        approved(**bad)


def test_endpoint_auth_and_bounds(monkeypatch):
    token = "test-token-" + "x"*40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/statistics/bayesian/"
    headers = {"Authorization": "Bearer " + token}
    data = approved().model_dump()
    assert client.post(url+"review", json=data["plan"]).status_code == 401
    assert client.post(url+"review", json=data["plan"], headers=headers).json()["review_sha256"] == data["review_sha256"]
    response = client.post(url+"run", json=data, headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert client.post(url+"run", json={**data, "consent": "true"}, headers=headers).status_code == 422
    assert client.post(url+"run", content=b"x"*8193, headers=headers).status_code == 413
