import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_research_perspectives import PerspectiveRequest, compare_perspectives, register
from studio_research_uncertainty import UncertaintyRequest, inventory
from test_studio_research_uncertainty import payload as uncertainty_data


def payload():
    data = uncertainty_data()
    return {
        "uncertainty_request": data,
        "uncertainty_review_sha256": inventory(
            UncertaintyRequest.model_validate(data))["uncertainty_review_sha256"],
        "perspectives": [
            {"id": "view_a", "label": "First view", "claim_ids": ["first"]},
            {"id": "view_b", "label": "Second view", "claim_ids": ["second"]},
        ],
    }


def result(data):
    return compare_perspectives(PerspectiveRequest.model_validate(data))


def test_perspectives_preserve_source_sharing_and_conflicts():
    data = payload()
    out = result(data)
    assert out == result(data)
    pair = out["comparisons"][0]
    assert pair["shared_claim_ids"] == []
    assert len(pair["shared_source_ids"]) == 2
    assert pair["potential_conflict_count"] == 1
    assert pair["cross_view_claim_comparisons"][0]["contradiction_verified"] is False
    assert out["unassigned_claim_ids"] == []
    assert all(view["unresolved_item_ids"] for view in out["perspectives"])
    assert out["perspective_ranking_performed"] is False
    assert out["independent_verification"] is False
    assert out["execution_authorized"] is False
    assert "Unverified excerpt" not in str(out)


def test_shared_claim_is_not_cross_view_conflict():
    data = payload()
    data["perspectives"][1]["claim_ids"].append("first")
    out = result(data)
    pair = out["comparisons"][0]
    assert pair["shared_claim_ids"] == ["claim:first"]
    assert pair["cross_view_claim_comparisons"] == []
    assert pair["potential_conflict_count"] == 0
    assert all(view["claim_source_links"] for view in out["perspectives"])


def test_unassigned_claim_is_visible():
    data = payload()
    data["perspectives"][1]["claim_ids"] = ["first"]
    assert result(data)["unassigned_claim_ids"] == ["claim:second"]


@pytest.mark.parametrize("change", ["id", "unknown", "duplicate_claim", "stale", "empty"])
def test_invalid_perspective(change):
    data = payload()
    if change == "id":
        data["perspectives"][1]["id"] = "view_a"
    elif change == "unknown":
        data["perspectives"][1]["claim_ids"] = ["unknown"]
    elif change == "duplicate_claim":
        data["perspectives"][0]["claim_ids"].append("first")
    elif change == "stale":
        data["uncertainty_review_sha256"] = "0" * 64
    else:
        data["perspectives"][0]["label"] = "  "
    with pytest.raises(ValueError):
        result(data)


def test_digest_binds_view_without_changing_source_identity():
    data = payload()
    original = result(data)
    data["perspectives"][0]["label"] = "Renamed view"
    out = result(data)
    assert out["perspective_review_sha256"] != original["perspective_review_sha256"]
    assert out["comparisons"] == original["comparisons"]


def test_endpoint_auth_and_bounds(monkeypatch):
    token = "test-token-" + "x" * 40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/research/perspective-review"
    headers = {"Authorization": "Bearer " + token}
    assert client.post(url, json=payload()).status_code == 401
    response = client.post(url, json=payload(), headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["comparisons"][0]["potential_conflict_count"] == 1
    data = payload()
    data["perspectives"][0]["claim_ids"] = ["unknown"]
    assert client.post(url, json=data, headers=headers).status_code == 422
    assert client.post(url, content=b"x" * 262145, headers=headers).status_code == 413
