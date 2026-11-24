import copy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_research_graph import GraphRequest, graph
from studio_research_conflicts import ConflictRequest, compare_claims, register
from test_studio_research_graph import payload


def request_data():
    original = payload()
    scope = {"population": "adults", "setting": "clinic", "period": "year_one",
             "measurement": "measure_a", "conditions": "protocol_a"}
    return {"graph_request": original,
            "graph_sha256": graph(GraphRequest.model_validate(original))["graph_sha256"],
            "frames": [
                {"claim_id": "first", "proposition_id": "effect_a",
                 "polarity": "affirms", "scope": dict(scope)},
                {"claim_id": "second", "proposition_id": "effect_a",
                 "polarity": "denies", "scope": dict(scope)},
            ]}


def result(data):
    return compare_claims(ConflictRequest.model_validate(data))


def test_opposite_claims_are_candidates_not_verified_conflicts():
    data = request_data()
    out = result(data)
    assert out == result(data)
    assert out["potential_conflict_count"] == 1
    item = out["comparisons"][0]
    assert item["status"] == "potential_conflict_requires_review"
    assert item["contradiction_verified"] is False
    assert len(item["shared_source_ids"]) == 2
    assert len(item["shared_source_opposite_stance_ids"]) == 1
    assert out["semantic_inference"] is False
    assert out["execution_authorized"] is False


@pytest.mark.parametrize("field", ["population", "setting", "period", "measurement", "conditions"])
def test_different_or_unknown_scope_is_not_a_conflict(field):
    data = request_data()
    data["frames"][1]["scope"][field] = "different"
    out = result(data)
    assert out["potential_conflict_count"] == 0
    assert out["comparisons"][0]["different_scope_fields"] == [field]
    assert out["comparisons"][0]["status"] == "different_reported_scope"
    data["frames"][1]["scope"][field] = None
    out = result(data)
    assert out["comparisons"][0]["status"] == "scope_unresolved"
    assert out["comparisons"][0]["unknown_scope_fields"] == [field]


def test_unknown_on_both_sides_is_not_equal_scope():
    data = request_data()
    for frame in data["frames"]:
        frame["scope"] = {}
    assert result(data)["comparisons"][0]["status"] == "scope_unresolved"


def test_different_kind_and_polarity():
    data = request_data()
    data["graph_request"]["claims"][1]["reasoning"]["claim_kind"] = "association"
    data["graph_sha256"] = graph(GraphRequest.model_validate(data["graph_request"]))["graph_sha256"]
    assert result(data)["comparisons"][0]["status"] == "different_claim_kind"
    data = request_data()
    data["frames"][1]["polarity"] = "affirms"
    assert result(data)["comparisons"][0]["status"] == "same_reported_polarity"
    data["frames"][1]["polarity"] = "uncertain"
    assert result(data)["comparisons"][0]["status"] == "polarity_unresolved"


def test_different_propositions_and_missing_frames():
    data = request_data()
    data["frames"][1]["proposition_id"] = "other"
    assert result(data)["comparisons"] == []
    data["frames"].pop()
    assert result(data)["unframed_claim_ids"] == ["second"]


def test_stale_graph_and_invalid_frames():
    data = request_data()
    data["graph_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        result(data)
    data = request_data()
    data["frames"].append(copy.deepcopy(data["frames"][0]))
    with pytest.raises(ValueError):
        result(data)
    data = request_data()
    data["frames"][0]["claim_id"] = "missing"
    with pytest.raises(ValueError):
        result(data)


def test_digest_binds_scope():
    data = request_data()
    before = result(data)["conflict_review_sha256"]
    data["frames"][0]["scope"]["period"] = "later"
    assert result(data)["conflict_review_sha256"] != before


def test_endpoint_auth_and_bounds(monkeypatch):
    token = "test-token-" + "x" * 40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/research/conflict-review"
    headers = {"Authorization": "Bearer " + token}
    assert client.post(url, json=request_data()).status_code == 401
    response = client.post(url, json=request_data(), headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["potential_conflict_count"] == 1
    data = request_data()
    data["frames"][0]["polarity"] = "verified"
    assert client.post(url, json=data, headers=headers).status_code == 422
    assert client.post(url, content=b"x" * 262145, headers=headers).status_code == 413
