import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_research_critique import CritiqueRequest, critique
from studio_research_synthesis import SynthesisRequest, synthesize, register
from studio_research_uncertainty import inventory
from test_studio_research_critique import candidate_data


def payload():
    data = candidate_data()
    return {"review": data,
            "reference_draft_sha256": critique(CritiqueRequest.model_validate(data))["reference_draft_sha256"]}


def result(data):
    return synthesize(SynthesisRequest.model_validate(data))


def test_synthesis_keeps_shared_references_and_claim_specific_stance():
    data = payload()
    out = result(data)
    assert out == result(data)
    assert len(out["claims"]) == 2 and len(out["references"]) == 2
    assert [row["number"] for row in out["references"]] == [1, 2]
    assert out["references"][0]["url"] == "https://doi.org/10.1234/abc"
    first, second = out["claims"]
    assert first["reference_links"][0]["reference_number"] == second["reference_links"][0]["reference_number"]
    assert first["reference_links"][0]["relation"] == "caller_reported_supports"
    assert second["reference_links"][0]["relation"] == "caller_reported_challenges"
    assert all(row["status"] == "incomplete_unverified" for row in out["references"])
    assert "author" in out["references"][0]["missing_metadata"]
    assert "caller_supplied_claim" not in first
    assert "Unverified excerpt" not in str(out)
    assert "A test claim" not in str(out)
    assert out["human_review_required"] and not out["independent_verification"]
    assert not out["execution_authorized"]


def test_all_uncertainties_and_conflicts_remain_visible():
    data = payload()
    model = SynthesisRequest.model_validate(data)
    upstream = inventory(model.review.perspective_request.uncertainty_request)
    out = result(data)
    assert out["uncertainties"] == upstream["entries"]
    assert out["claim_comparisons"][0]["status"] == "potential_conflict_requires_review"
    assert out["claim_comparisons"][0]["contradiction_verified"] is False
    assert len(out["perspectives"]) == 2
    assert out["unassigned_claim_ids"] == []
    data["include_claim_text"] = True
    full = result(data)
    assert full["claims"][0]["caller_supplied_claim"] == "A test claim"
    assert full["report_sha256"] != out["report_sha256"]


def test_stale_or_damaged_draft_rejected():
    data = payload()
    data["review"]["candidate"]["unresolved_item_ids"].pop()
    with pytest.raises(ValueError, match="revision"):
        result(data)
    data = payload()
    data["reference_draft_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="Stale"):
        result(data)


def test_reference_draft_without_candidate_is_allowed():
    data = payload()
    expected = result(data)
    data["review"]["candidate"] = None
    assert result(data) == expected


def test_endpoint_auth_and_bounds(monkeypatch):
    token = "test-token-" + "x" * 40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/research/synthesis"
    headers = {"Authorization": "Bearer " + token}
    data = payload()
    assert client.post(url, json=data).status_code == 401
    response = client.post(url, json=data, headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["status"] == "research_synthesis_draft"
    assert client.post(url, json={**data, "include_claim_text": "true"}, headers=headers).status_code == 422
    assert client.post(url, content=b"x" * 393217, headers=headers).status_code == 413
