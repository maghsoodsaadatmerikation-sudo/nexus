import math
import statistics

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_regression import ApprovedRegression, RegressionPlan, preview, run, register


def approved(x, y):
    plan = RegressionPlan.model_validate({
        "observations": [{"x": a, "y": b} for a, b in zip(x, y)]
    })
    return ApprovedRegression(plan=plan, review_sha256=preview(plan)["review_sha256"], consent=True)


def test_exact_line_and_direction():
    out = run(approved([1, 2, 3, 4], [5, 7, 9, 11]))
    fit = out["fit"]
    assert fit["slope"] == 2 and fit["intercept"] == 3
    assert fit["r_squared"] == 1 and fit["residual_sum_of_squares"] == 0
    assert out["correlations"] == {"pearson_r": 1, "spearman_rho_average_ties": 1}
    assert not out["causal_inference"] and not out["prediction_validated"]
    reverse = run(approved([1, 2, 3, 4], [-5, -7, -9, -11]))
    assert reverse["fit"]["slope"] == -2
    assert reverse["correlations"]["spearman_rho_average_ties"] == -1


def test_nonperfect_fit_against_stdlib_reference():
    x, y = [1, 2, 3, 4, 5], [2, 4, 3, 7, 5]
    out = run(approved(x, y))
    slope, intercept = statistics.linear_regression(x, y)
    sse = math.fsum((b - (slope*a + intercept))**2 for a, b in zip(x, y))
    assert out["fit"]["slope"] == pytest.approx(slope)
    assert out["fit"]["intercept"] == pytest.approx(intercept)
    assert out["fit"]["residual_sum_of_squares"] == pytest.approx(sse)
    assert out["correlations"]["pearson_r"] == pytest.approx(statistics.correlation(x, y))
    assert out["fit"]["standardized_slope"] == out["correlations"]["pearson_r"]
    assert out["fit"]["training_rmse"] == pytest.approx(math.sqrt(sse/len(x)))


def test_rank_correlation_average_ties():
    out = run(approved([1, 1, 3, 4], [1, 2, 2, 4]))
    expected = statistics.correlation([1.5, 1.5, 3, 4], [1, 2.5, 2.5, 4])
    assert out["correlations"]["spearman_rho_average_ties"] == pytest.approx(expected)
    assert "predictor_ties_present" in out["diagnostics"]


def test_degenerate_inputs_and_large_offsets():
    constant_x = run(approved([3, 3, 3], [1, 2, 3]))
    assert constant_x["fit"] is None
    assert constant_x["correlations"]["pearson_r"] is None
    constant_y = run(approved([1, 2, 3], [4, 4, 4]))
    assert constant_y["fit"]["slope"] == 0 and constant_y["fit"]["r_squared"] is None
    assert constant_y["correlations"]["spearman_rho_average_ties"] is None
    offset = 10**12 - 3
    out = run(approved([offset, offset+1, offset+2], [1, 2, 3]))
    assert out["fit"]["slope"] == 1 and out["fit"]["intercept"] == 1-offset
    assert out["fit"]["residual_sum_of_squares"] == 0


def test_consent_and_stale_plan():
    data = approved([1, 2, 3], [2, 4, 6])
    assert run(data) == run(data)
    with pytest.raises(ValueError):
        run(data.model_copy(update={"consent": False}))
    with pytest.raises(ValueError):
        run(data.model_copy(update={"plan": approved([1, 2, 4], [2, 4, 6]).plan}))


@pytest.mark.parametrize("bad", [True, 1.5, 10**13, "1"])
def test_invalid_observations(bad):
    with pytest.raises(ValueError):
        RegressionPlan.model_validate({"observations": [{"x": bad, "y": 1}]*3})


def test_endpoints_auth_and_bounds(monkeypatch):
    token = "test-token-" + "x"*40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/statistics/regression/"
    headers = {"Authorization": "Bearer " + token}
    data = approved([1, 2, 3], [2, 4, 6]).model_dump()
    assert client.post(url+"review", json=data["plan"]).status_code == 401
    assert client.post(url+"review", json=data["plan"], headers=headers).json()["review_sha256"] == data["review_sha256"]
    response = client.post(url+"run", json=data, headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["fit"]["slope"] == 2
    assert client.post(url+"run", json={**data, "consent": "true"}, headers=headers).status_code == 422
    assert client.post(url+"run", content=b"x"*131073, headers=headers).status_code == 413
