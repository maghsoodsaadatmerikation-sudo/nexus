import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_sensitivity import ApprovedSensitivity, ReviewRequest, preview, run, register


def meta_plan():
    return {"method": "leave_one_out", "baseline": {
        "studies": [{"study_id": f"s{i}", "effect": effect, "standard_error": 1}
                    for i, effect in enumerate([1, 2, 9])],
        "effect_scale": "mean_difference",
        "independent_estimates_reported": True, "comparable_estimands_reported": True,
        "valid_standard_errors_reported": True,
    }}


def bayes_plan():
    return {"method": "prior_sensitivity", "baseline": {
        "prior_alpha": 1, "prior_beta": 1, "successes": 7, "failures": 3,
        "independent_trials_reported": True, "common_probability_reported": True,
    }, "alternative_priors": [{"alpha": 2, "beta": 8}, {"alpha": 8, "beta": 2}]}


def approved(data):
    plan = ReviewRequest.model_validate({"plan": data}).plan
    return ApprovedSensitivity(plan=plan, review_sha256=preview(plan)["review_sha256"], consent=True)


def test_leave_one_out_recomputes_both_models_and_keeps_all_scenarios():
    data = approved(meta_plan())
    out = run(data)
    assert out == run(data)
    assert out["baseline"]["common_effect"]["effect"] == pytest.approx(4)
    assert [r["excluded_study_id"] for r in out["scenario_results"]] == ["s0", "s1", "s2"]
    assert [r["common_effect"]["effect"] for r in out["scenario_results"]] == pytest.approx([5.5, 5, 1.5])
    assert out["scenario_results"][2]["random_effect_change"] == pytest.approx(-2.5)
    assert out["observed_ranges"]["common_effect"] == {"minimum": 1.5, "maximum": 5.5}
    assert not out["robustness_verified"] and not out["causal_inference"]


def test_bayesian_prior_changes_hold_data_fixed():
    out = run(approved(bayes_plan()))
    assert out["baseline"]["mean"] == pytest.approx(8/12)
    assert [r["posterior"]["mean"] for r in out["scenario_results"]] == pytest.approx([9/20, 15/20])
    assert out["observed_ranges"]["mean"] == {"minimum": 9/20, "maximum": 15/20}
    assert out["scenario_results"][0]["posterior"]["alpha"] == 9
    assert out["scenario_results"][0]["posterior"]["beta"] == 11


def test_assumption_gate_and_digest():
    data = meta_plan()
    data["baseline"]["independent_estimates_reported"] = False
    out = run(approved(data))
    assert out["baseline"] is None and out["scenario_results"] == []
    data = approved(bayes_plan())
    with pytest.raises(ValueError):
        run(data.model_copy(update={"consent": False}))
    with pytest.raises(ValueError):
        run(data.model_copy(update={"review_sha256": "0"*64}))


@pytest.mark.parametrize("bad", ["too_few_studies", "duplicate_prior", "baseline_prior", "invalid_prior"])
def test_invalid_scenarios(bad):
    data = meta_plan() if bad == "too_few_studies" else bayes_plan()
    if bad == "too_few_studies":
        data["baseline"]["studies"].pop()
    elif bad == "duplicate_prior":
        data["alternative_priors"].append(data["alternative_priors"][0])
    elif bad == "baseline_prior":
        data["alternative_priors"].append({"alpha": 1, "beta": 1})
    else:
        data["alternative_priors"][0]["alpha"] = True
    with pytest.raises(ValueError):
        approved(data)


def test_endpoint_auth_and_bounds(monkeypatch):
    token = "test-token-" + "x"*40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/statistics/sensitivity/"
    headers = {"Authorization": "Bearer " + token}
    data = approved(bayes_plan()).model_dump()
    assert client.post(url+"review", json={"plan": data["plan"]}).status_code == 401
    response = client.post(url+"review", json={"plan": data["plan"]}, headers=headers)
    assert response.status_code == 200
    assert response.json()["review_sha256"] == data["review_sha256"]
    response = client.post(url+"run", json=data, headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert client.post(url+"run", json={**data, "consent": "true"}, headers=headers).status_code == 422
    assert client.post(url+"run", content=b"x"*65537, headers=headers).status_code == 413
