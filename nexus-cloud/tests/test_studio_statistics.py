import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_statistics import ApprovedPlan, PairedPlan, preview, run, register


def approved(differences, **overrides):
    plan = PairedPlan.model_validate({
        "pairs": [{"before": 0, "after": d} for d in differences],
        "independent_pairs_reported": True, "pairing_valid_reported": True,
        **overrides,
    })
    return ApprovedPlan(plan=plan, review_sha256=preview(plan)["review_sha256"], consent=True)


def test_exact_sign_test_and_wilson_known_values():
    data = approved([1]*8)
    out = run(data)
    assert out == run(data)
    assert out["inference"]["two_sided_p_value"] == 0.0078125
    interval = out["inference"]["positive_fraction_interval"]
    assert interval["lower"] == pytest.approx(0.6755924)
    assert interval["upper"] == pytest.approx(1)
    assert out["descriptive"]["sample_sd_change"] == 0
    assert not out["assumptions_verified"] and not out["causal_inference"]


def test_ties_and_direction_preserved():
    out = run(approved([-2, 0, 1, 3]))
    d = out["descriptive"]
    assert d["mean_change"] == 0.5 and d["median_change"] == 0.5
    assert d["sample_sd_change"] == pytest.approx(2.081665999)
    assert (d["positive"], d["negative"], d["ties"]) == (2, 1, 1)
    assert out["inference"]["nonzero_pairs"] == 3
    assert out["inference"]["two_sided_p_value"] == 1
    assert d["positive_fraction_among_nonzero"] == pytest.approx(2/3)
    reverse = run(approved([2, 0, -1, -3]))
    assert reverse["descriptive"]["mean_change"] == -d["mean_change"]
    assert reverse["inference"]["two_sided_p_value"] == out["inference"]["two_sided_p_value"]


def test_assumption_gate_and_all_ties():
    out = run(approved([1, 2], independent_pairs_reported=False))
    assert out["inference"] is None
    assert out["inference_status"] == "assumptions_not_reported"
    out = run(approved([0, 0]))
    assert out["inference"] is None
    assert out["inference_status"] == "all_differences_zero"


def test_large_exact_tail_finite():
    out = run(approved([1]*1000, confidence=99))
    assert 0 < out["inference"]["two_sided_p_value"] < 1e-200
    assert out["inference"]["positive_fraction_interval"]["confidence_percent"] == 99


def test_digest_and_consent():
    data = approved([1, 2])
    with pytest.raises(ValueError):
        run(data.model_copy(update={"consent": False}))
    with pytest.raises(ValueError):
        run(data.model_copy(update={"plan": approved([2, 3]).plan}))


@pytest.mark.parametrize("pair", [{"before": True, "after": 1},
                                  {"before": 0, "after": 1.5},
                                  {"before": 0, "after": 10**13}])
def test_invalid_pair(pair):
    with pytest.raises(ValueError):
        PairedPlan.model_validate({"pairs": [pair, pair]})


def test_endpoint_auth_and_bounds(monkeypatch):
    token = "test-token-" + "x"*40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/statistics/paired/"
    headers = {"Authorization": "Bearer " + token}
    data = approved([1, 2]).model_dump()
    assert client.post(url+"review", json=data["plan"]).status_code == 401
    response = client.post(url+"review", json=data["plan"], headers=headers)
    assert response.status_code == 200
    assert response.json()["review_sha256"] == data["review_sha256"]
    response = client.post(url+"run", json=data, headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert client.post(url+"run", json={**data, "consent": "true"}, headers=headers).status_code == 422
    assert client.post(url+"run", content=b"x"*131073, headers=headers).status_code == 413
