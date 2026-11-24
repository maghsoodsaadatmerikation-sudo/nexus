import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_research_conflicts import ConflictRequest, compare_claims
from studio_research_uncertainty import UncertaintyRequest, inventory, register
from test_studio_research_conflicts import request_data as conflict_data


def payload():
    data = conflict_data()
    return {"conflict_request": data,
            "conflict_review_sha256": compare_claims(
                ConflictRequest.model_validate(data))["conflict_review_sha256"]}


def result(data):
    return inventory(UncertaintyRequest.model_validate(data))


def rebind(data):
    data["conflict_review_sha256"] = compare_claims(
        ConflictRequest.model_validate(data["conflict_request"]))["conflict_review_sha256"]


def test_uncertainty_preserves_conflicts_and_review_boundaries():
    data = payload()
    out = result(data)
    assert out == result(data)
    assert out["status"] == "human_review_required"
    assert out["unresolved_count"] == len(out["entries"]) == sum(out["category_counts"].values())
    assert len({item["id"] for item in out["entries"]}) == len(out["entries"])
    codes = {item["code"] for item in out["entries"]}
    assert {"potential_claim_conflict", "shared_source_interpretation_differs",
            "causal_identification_not_verified", "independent_verification_missing"} <= codes
    assert all(item["status"] == "unresolved" and item["review_action"] for item in out["entries"])
    assert out["probability_estimated"] is False
    assert out["completeness_guaranteed"] is False
    assert out["independent_verification"] is False
    assert out["execution_authorized"] is False
    assert "Unverified excerpt" not in str(out)


def test_unknown_scope_does_not_become_false_conflict():
    data = payload()
    data["conflict_request"]["frames"][0]["scope"]["period"] = None
    rebind(data)
    out = result(data)
    assert not any(item["code"] == "potential_claim_conflict" for item in out["entries"])
    entry = next(item for item in out["entries"] if item["code"] == "comparison_scope_unknown")
    assert entry["fields"] == ["period"]


def test_unframed_claim_and_stale_digest():
    data = payload()
    data["conflict_request"]["frames"].pop()
    with pytest.raises(ValueError, match="Stale"):
        result(data)
    rebind(data)
    assert any(item["code"] == "claim_frame_missing" and item["target"] == ["claim:second"]
               for item in result(data)["entries"])


def test_scope_and_kind_findings_are_not_hidden_by_status_priority():
    data = payload()
    data["conflict_request"]["frames"][0]["scope"]["population"] = "other"
    data["conflict_request"]["frames"][0]["scope"]["period"] = None
    rebind(data)
    codes = {item["code"] for item in result(data)["entries"]}
    assert {"comparison_scope_unknown", "comparison_scope_different"} <= codes


def test_endpoint_auth_and_bounds(monkeypatch):
    token = "test-token-" + "x" * 40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/research/uncertainty-review"
    headers = {"Authorization": "Bearer " + token}
    assert client.post(url, json=payload()).status_code == 401
    response = client.post(url, json=payload(), headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    data = payload()
    data["conflict_review_sha256"] = "0" * 64
    assert client.post(url, json=data, headers=headers).status_code == 422
    assert client.post(url, content=b"x" * 262145, headers=headers).status_code == 413
