import math

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_meta_analysis import ApprovedMeta, MetaPlan, preview, run, register


def approved(effects=(1, 3), errors=(1, 1), **overrides):
    plan = MetaPlan.model_validate({
        "studies": [{"study_id": f"s{i}", "effect": e, "standard_error": se}
                    for i, (e, se) in enumerate(zip(effects, errors))],
        "effect_scale": "mean_difference",
        "independent_estimates_reported": True, "comparable_estimands_reported": True,
        "valid_standard_errors_reported": True, **overrides,
    })
    return ApprovedMeta(plan=plan, review_sha256=preview(plan)["review_sha256"], consent=True)


def test_two_study_analytic_fixture():
    out = run(approved())
    assert out == run(approved())
    common, random = out["common_effect"], out["random_effects"]
    assert common["effect"] == random["effect"] == 2
    assert common["standard_error"] == pytest.approx(math.sqrt(0.5))
    assert random["standard_error"] == pytest.approx(1)
    h = out["heterogeneity"]
    assert h["cochran_q"] == 2 and h["degrees_of_freedom"] == 1
    assert h["i_squared_percent"] == 50 and h["tau_squared"] == 1
    assert common["confidence_interval"]["lower"] == pytest.approx(0.61409617565)
    assert random["confidence_interval"]["upper"] == pytest.approx(3.95996398454)
    assert not out["causal_inference"] and not out["assumptions_verified"]


def test_unequal_weights_and_zero_heterogeneity():
    out = run(approved((2, 2, 2), (1, 2, 3)))
    assert out["common_effect"] == out["random_effects"]
    assert out["heterogeneity"]["tau_squared"] == 0
    assert out["heterogeneity"]["i_squared_percent"] == 0
    weights = out["common_effect"]["weights"]
    assert weights[0]["fraction"] == pytest.approx(36/49)
    assert sum(w["fraction"] for w in weights) == pytest.approx(1)
    assert "zero_estimated_heterogeneity_not_proof_of_homogeneity" in out["diagnostics"]


def test_extreme_weight_imbalance_and_log_scale_remains_finite():
    out = run(approved((1, -1, 2), (1e-6, 1e6, 1e6),
                       effect_scale="log_risk_ratio", confidence=99))
    assert out["effect_scale"] == "log_risk_ratio"
    assert math.isfinite(out["heterogeneity"]["tau_squared"])
    assert "common_effect_dominated_by_one_study" in out["diagnostics"]
    for key in ("common_effect", "random_effects"):
        assert sum(w["fraction"] for w in out[key]["weights"]) == pytest.approx(1)
        assert math.isfinite(out[key]["standard_error"])


def test_assumption_gate_and_consent():
    out = run(approved(comparable_estimands_reported=False))
    assert out["common_effect"] is None and out["heterogeneity"] is None
    data = approved()
    with pytest.raises(ValueError):
        run(data.model_copy(update={"consent": False}))
    with pytest.raises(ValueError):
        run(data.model_copy(update={"plan": approved((1, 4)).plan}))


@pytest.mark.parametrize("error", [0, -1, float("inf"), float("nan"), True, "1", 1e-7])
def test_invalid_standard_error(error):
    with pytest.raises(ValueError):
        approved(errors=(1, error))


def test_duplicate_study_id():
    data = approved().plan.model_dump()
    data["studies"][1]["study_id"] = data["studies"][0]["study_id"]
    with pytest.raises(ValueError):
        preview(MetaPlan.model_validate(data))


def test_endpoint_auth_and_bounds(monkeypatch):
    token = "test-token-" + "x"*40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/statistics/meta-analysis/"
    headers = {"Authorization": "Bearer " + token}
    data = approved().model_dump()
    assert client.post(url+"review", json=data["plan"]).status_code == 401
    assert client.post(url+"review", json=data["plan"], headers=headers).json()["review_sha256"] == data["review_sha256"]
    response = client.post(url+"run", json=data, headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert client.post(url+"run", json={**data, "consent": "true"}, headers=headers).status_code == 422
    assert client.post(url+"run", content=b"x"*65537, headers=headers).status_code == 413
