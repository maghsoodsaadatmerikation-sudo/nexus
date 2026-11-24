import copy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_analysis_batch import ApprovedBatch, Batch, preview, register, run


def payload():
    return {
        "plan": {"goal": "Analyze supplied data", "steps": [
            {"id": "numbers", "tool": "analysis", "description": "Summarize values",
             "depends_on": ["text"]},
            {"id": "text", "tool": "analysis", "description": "Count text"},
        ]},
        "operations": [
            {"step_id": "numbers", "operation": "numeric.summary", "values": [7, -1, 2, 4]},
            {"step_id": "text", "operation": "text.metrics", "text": "سلام world\n"},
        ],
    }


def approved(data):
    return {"batch": data, "review_sha256": preview(Batch.model_validate(data))["review_sha256"],
            "consent": True}


def test_real_computation_in_dependency_order():
    data = payload()
    review = preview(Batch.model_validate(data))
    assert review["review_order"] == ["text", "numbers"]
    assert review["operations"][0]["input"]["text"] == "سلام world\n"
    assert "results" not in review
    result = run(ApprovedBatch.model_validate(approved(data)))
    assert result["status"] == "computed"
    assert result["external_execution_authorized"] is False
    assert result["results"][0]["metrics"] == {
        "characters": 11, "utf8_bytes": 15, "whitespace_tokens": 2, "lines": 1,
    }
    assert result["results"][1]["metrics"] == {
        "count": 4, "sum": 12, "min": -1, "max": 7, "mean": 3.0, "median": 3.0,
    }


def test_changed_input_cannot_reuse_review():
    data = approved(payload())
    data["batch"]["operations"][0]["values"][0] = 9
    with pytest.raises(ValueError):
        run(ApprovedBatch.model_validate(data))


@pytest.mark.parametrize("change", ["unsupported", "missing", "duplicate", "cycle", "extra"])
def test_invalid_plans_and_tools(change):
    data = payload()
    if change == "unsupported":
        data["plan"]["steps"][0]["tool"] = "connector"
    elif change == "missing":
        data["operations"].pop()
    elif change == "duplicate":
        data["operations"][1] = copy.deepcopy(data["operations"][0])
    elif change == "cycle":
        data["plan"]["steps"][1]["depends_on"] = ["numbers"]
    else:
        data["operations"][0]["command"] = "arbitrary"
    with pytest.raises(ValueError):
        preview(Batch.model_validate(data))


@pytest.mark.parametrize("values", [[], [True], [1.2], [10**12 + 1], [1] * 1001])
def test_numeric_bounds(values):
    data = payload()
    data["operations"][0]["values"] = values
    with pytest.raises(ValueError):
        Batch.model_validate(data)


def test_endpoint_consent_auth_and_bounds(monkeypatch):
    token = "test-token-" + "x" * 40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    headers = {"Authorization": "Bearer " + token}
    base = "/studio/api/analysis-batch"
    assert client.post(base + "/review", json=payload()).status_code == 401
    assert client.post(base + "/run", json=approved(payload())).status_code == 401
    review = client.post(base + "/review", json=payload(), headers=headers)
    assert review.status_code == 200
    assert review.headers["cache-control"] == "no-store"
    request = approved(payload())
    response = client.post(base + "/run", json=request, headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["status"] == "computed"
    for consent in [False, "true", 1]:
        bad = {**request, "consent": consent}
        assert client.post(base + "/run", json=bad, headers=headers).status_code == 422
    assert client.post(base + "/review", content=b"x" * 65537, headers=headers).status_code == 413
