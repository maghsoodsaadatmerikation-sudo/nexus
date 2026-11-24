import math
import statistics

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_regression_diagnostics import ApprovedDiagnostics, DiagnosticPlan, preview, run, register


def approved(x, y):
    plan = DiagnosticPlan.model_validate({"regression": {
        "observations": [{"x": a, "y": b} for a, b in zip(x, y)]}})
    return ApprovedDiagnostics(plan=plan, review_sha256=preview(plan)["review_sha256"], consent=True)


def test_diagnostics_match_independent_formulas_and_deleted_refits():
    x, y = [1, 2, 3, 4, 5, 12], [2, 4, 5, 8, 10, -2]
    data = approved(x, y)
    out = run(data)
    assert out == run(data)
    slope, intercept = statistics.linear_regression(x, y)
    residuals = [b-(slope*a+intercept) for a, b in zip(x, y)]
    mse = sum(e*e for e in residuals)/(len(x)-2)
    assert sum(r["leverage"] for r in out["observations"]) == pytest.approx(2)
    assert sum(r["residual"]**2 for r in out["observations"]) == pytest.approx(sum(e*e for e in residuals))
    for i, row in enumerate(out["observations"]):
        h = 1/len(x)+(x[i]-statistics.mean(x))**2/sum((a-statistics.mean(x))**2 for a in x)
        assert row["leverage"] == pytest.approx(h)
        assert row["residual"] == pytest.approx(residuals[i])
        assert row["internal_studentized_residual"] == pytest.approx(residuals[i]/math.sqrt(mse*(1-h)))
        assert row["cooks_distance"] == pytest.approx(residuals[i]**2*h/(2*mse*(1-h)**2))
        deleted = statistics.linear_regression(x[:i]+x[i+1:], y[:i]+y[i+1:]).slope
        assert row["leave_one_out_slope"] == pytest.approx(deleted)
        assert row["slope_change"] == pytest.approx(deleted-slope)
    assert "high_leverage" in out["observations"][-1]["flags"]
    assert "large_cooks_distance" in out["observations"][-1]["flags"]
    assert not out["automatic_exclusions"] and not out["bias_verified"]


def test_undefined_cases_and_large_offset():
    out = run(approved([1, 1, 1, 1], [1, 2, 3, 4]))
    assert out["diagnostic_status"] == "constant_predictor" and out["observations"] == []
    out = run(approved([1, 2, 3, 4], [2, 4, 6, 8]))
    assert out["diagnostic_status"] == "zero_residual_variance"
    assert all(r["cooks_distance"] is None and r["internal_studentized_residual"] is None for r in out["observations"])
    out = run(approved([1, 1, 1, 9], [1, 3, 2, 7]))
    last = out["observations"][-1]
    assert last["leverage"] == 1 and last["cooks_distance"] is None
    assert last["leave_one_out_slope"] is None
    assert "deleted_fit_has_constant_predictor" in last["flags"]
    off = 10**12-10
    out = run(approved([off+i for i in range(4)], [1, 2, 3, 4]))
    assert all(r["residual"] == 0 for r in out["observations"])


def test_digest_and_consent():
    with pytest.raises(ValueError):
        approved([1, 2, 3], [1, 2, 3])
    data = approved([1, 2, 3, 4], [2, 3, 5, 7])
    with pytest.raises(ValueError):
        run(data.model_copy(update={"consent": False}))
    with pytest.raises(ValueError):
        run(data.model_copy(update={"review_sha256": "0"*64}))


def test_endpoints_auth_and_bounds(monkeypatch):
    token = "test-token-" + "x"*40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/statistics/diagnostics/"
    headers = {"Authorization": "Bearer " + token}
    data = approved([1, 2, 3, 4], [2, 3, 5, 7]).model_dump()
    assert client.post(url+"review", json=data["plan"]).status_code == 401
    assert client.post(url+"review", json=data["plan"], headers=headers).json()["review_sha256"] == data["review_sha256"]
    response = client.post(url+"run", json=data, headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert client.post(url+"run", json={**data, "consent": "true"}, headers=headers).status_code == 422
    assert client.post(url+"run", content=b"x"*131073, headers=headers).status_code == 413
