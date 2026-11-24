import hashlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_research_evidence import EvidenceRequest, review
from studio_research_reasoning import ReasoningRequest, assess, register
from test_studio_research_evidence import payload


def request_data(kind="causal", design="cohort"):
    evidence = payload()
    return {
        "evidence": evidence,
        "review_sha256": review(EvidenceRequest.model_validate(evidence))["review_sha256"],
        "claim_kind": kind,
        "annotations": [{
            "source_index": 1, "design": design,
            "excerpt_start": 0, "excerpt_end": 10,
            "population_match": "reported_match", "limitations_reviewed": True,
        }],
    }


def result(data):
    return assess(ReasoningRequest.model_validate(data))


def test_observational_causal_claim_is_not_established():
    data = request_data()
    out = result(data)
    assert out == result(data)
    assert out["status"] == "human_review_required"
    assert "no_supporting_causal_design_reported" in out["issues"]
    assert "reported_disagreement_requires_reconciliation" in out["issues"]
    assert "causal_identification_not_verified" in out["issues"]
    assert out["claim_verified"] is False and out["causality_established"] is False
    assert out["annotations"][0]["excerpt_sha256"] == hashlib.sha256(
        data["evidence"]["cards"][1]["excerpt"][:10].encode()).hexdigest()
    assert "Unverified excerpt" not in str(out)


def test_randomized_label_is_not_causal_proof():
    out = result(request_data(design="randomized_trial"))
    assert "no_supporting_causal_design_reported" not in out["issues"]
    assert "causal_identification_not_verified" in out["issues"]
    assert out["causality_established"] is False


@pytest.mark.parametrize("kind,issue", [
    ("hypothesis", "hypothesis_not_established_finding"),
    ("observation", "observation_not_generalizable_without_review"),
    ("association", "association_does_not_establish_causation"),
    ("prediction", "out_of_sample_validation_not_verified"),
])
def test_claim_type_boundaries(kind, issue):
    assert issue in result(request_data(kind))["issues"]


@pytest.mark.parametrize("change", ["metadata", "encyclopedia", "span", "duplicate", "missing", "stale"])
def test_invalid_annotations(change):
    data = request_data()
    item = data["annotations"][0]
    if change == "metadata":
        item["source_index"] = 0
    elif change == "encyclopedia":
        item["source_index"] = 2
    elif change == "span":
        item["excerpt_end"] = 100
    elif change == "duplicate":
        data["annotations"].append(dict(item))
    elif change == "missing":
        item["source_index"] = 59
    else:
        data["evidence"]["claim"] = "Changed claim"
    with pytest.raises(ValueError):
        result(data)


def test_missing_annotations_and_digest_changes():
    data = request_data()
    original = result(data)
    data["annotations"] = []
    out = result(data)
    assert "supporting_source_design_unannotated" in out["issues"]
    assert "applicability_unresolved" in out["issues"]
    assert out["reasoning_review_sha256"] != original["reasoning_review_sha256"]


def test_endpoint_auth_and_bounds(monkeypatch):
    token = "test-token-" + "x" * 40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/research/reasoning-review"
    headers = {"Authorization": "Bearer " + token}
    assert client.post(url, json=request_data()).status_code == 401
    response = client.post(url, json=request_data(), headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["execution_authorized"] is False
    data = request_data()
    data["annotations"][0]["limitations_reviewed"] = "true"
    assert client.post(url, json=data, headers=headers).status_code == 422
    assert client.post(url, content=b"x" * 262145, headers=headers).status_code == 413
