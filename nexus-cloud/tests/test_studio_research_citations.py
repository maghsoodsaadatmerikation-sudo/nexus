import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_research_citations import CitationRequest, citations, register
from studio_research_evidence import EvidenceRequest, review
from test_studio_research_evidence import payload


def request_data():
    evidence = payload()
    return {"evidence": evidence, "review_sha256": review(
        EvidenceRequest.model_validate(evidence))["review_sha256"],
        "selected_indices": [0, 1, 2]}


def result(data):
    return citations(CitationRequest.model_validate(data))


def rebind(data):
    data["review_sha256"] = review(EvidenceRequest.model_validate(data["evidence"]))["review_sha256"]


def test_deduplicated_citations_and_missing_fields():
    data = request_data()
    out = result(data)
    assert out == result(data)
    assert len(out["entries"]) == 2
    first = out["entries"][0]
    assert first["selected_source_indices"] == [0, 1]
    assert first["url"] == "https://doi.org/10.1234/abc"
    assert first["missing_metadata"] == ["author", "issued", "container-title"]
    assert out["csl_json"][0]["DOI"] == "10.1234/abc"
    assert "author" not in out["csl_json"][0]
    assert "issued" not in out["csl_json"][0]
    assert out["numbered_reference_draft"][0].startswith("[1]")
    assert out["independent_verification"] is False
    assert "Unverified excerpt" not in str(out)


def test_selection_and_reference_order():
    data = request_data()
    data["selected_indices"] = [2, 1]
    out = result(data)
    assert out["entries"][0]["selected_source_indices"] == [1]
    assert out["entries"][0]["related_source_indices"] == [0, 1]
    assert out["entries"][1]["url"] == "https://en.wikipedia.org/?curid=12"


def test_conflicting_titles_are_not_silently_resolved():
    data = request_data()
    data["evidence"]["cards"][1]["title"] = "Different title"
    rebind(data)
    out = result(data)
    assert out["entries"][0]["title_conflict"] is True
    assert out["entries"][0]["title"] is None
    assert "title" not in out["csl_json"][0]
    assert "Title conflict" in out["numbered_reference_draft"][0]


@pytest.mark.parametrize("indices", [[], [0, 0], [9], [True], [-1]])
def test_invalid_selection(indices):
    data = request_data()
    data["selected_indices"] = indices
    with pytest.raises(ValueError):
        result(data)


def test_changed_evidence_requires_new_review():
    data = request_data()
    data["evidence"]["cards"][0]["title"] = "Changed"
    with pytest.raises(ValueError):
        result(data)


def test_citation_endpoint_auth_and_bounds(monkeypatch):
    token = "test-token-" + "x" * 40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    headers = {"Authorization": "Bearer " + token}
    url = "/studio/api/research/citations"
    assert client.post(url, json=request_data()).status_code == 401
    response = client.post(url, json=request_data(), headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["status"] == "reference_draft"
    data = request_data()
    data["review_sha256"] = "0" * 64
    assert client.post(url, json=data, headers=headers).status_code == 422
    assert client.post(url, content=b"x" * 262145, headers=headers).status_code == 413
