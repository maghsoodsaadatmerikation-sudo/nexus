import copy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_research_evidence import EvidenceRequest, review, register


def card(engine, kind, url):
    return {"engine": engine, "kind": kind, "url": url, "title": "Example",
            "excerpt": "Unverified excerpt", "query": "example",
            "at": "2026-11-24T00:00:00Z", "license": "Provider terms"}


def payload():
    return {"claim": "A test claim", "cards": [
        card("crossref", "bibliographic-metadata-only", "https://doi.org/10.1234/ABC"),
        card("europepmc", "abstract-excerpt", "https://doi.org/10.1234/%61bc"),
        card("wikipedia", "encyclopedia-excerpt", "https://en.wikipedia.org/?curid=12"),
    ], "assessments": [{"source_index": 1, "stance": "supports"},
                       {"source_index": 2, "stance": "challenges"}]}


def result(data):
    return review(EvidenceRequest.model_validate(data))


def test_groups_same_doi_and_flags_reported_disagreement():
    data = payload()
    out = result(data)
    assert out == result(data)
    assert out["received_cards"] == 3 and out["distinct_source_identities"] == 2
    assert out["duplicate_cards"] == 1
    assert out["inventory"][0]["source_indices"] == [0, 1]
    assert out["inventory"][0]["providers"] == ["crossref", "europepmc"]
    assert out["reported_disagreement"] is True
    assert out["independent_verification"] is False
    assert out["execution_authorized"] is False
    assert "Unverified excerpt" not in str(out)


def test_same_source_disagreement_is_not_multiple_independent_sources():
    data = payload()
    data["cards"].append(copy.deepcopy(data["cards"][1]))
    data["assessments"].append({"source_index": 3, "stance": "challenges"})
    out = result(data)
    assert out["stance_counts"]["mixed"] == 1
    assert out["distinct_source_identities"] == 2


@pytest.mark.parametrize("url", ["http://doi.org/10.1234/x", "https://localhost/10.1234/x",
                                "https://doi.org.evil.test/10.1234/x",
                                "https://user@doi.org/10.1234/x",
                                "https://doi.org/10.1234/x?token=secret",
                                "https://doi.org/10.1234/x#frag"])
def test_reject_invalid_source_urls(url):
    data = payload()
    data["cards"][0]["url"] = url
    with pytest.raises(ValueError):
        result(data)


def test_metadata_cannot_support_claim():
    data = payload()
    data["assessments"].append({"source_index": 0, "stance": "supports"})
    with pytest.raises(ValueError):
        result(data)
    data["assessments"] = []
    assert result(data)["stance_counts"]["unassessed_or_unclear"] == 2


def test_digest_binds_exact_input_and_assessments():
    data = payload()
    before = result(data)["review_sha256"]
    data["cards"][1]["excerpt"] = "Changed excerpt"
    assert result(data)["review_sha256"] != before


def test_endpoint_auth_and_bounds(monkeypatch):
    token = "test-token-" + "x" * 40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/research/evidence-review"
    headers = {"Authorization": "Bearer " + token}
    assert client.post(url, json=payload()).status_code == 401
    response = client.post(url, json=payload(), headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["reported_disagreement"] is True
    data = payload()
    data["assessments"].append({"source_index": 1, "stance": "unclear"})
    assert client.post(url, json=data, headers=headers).status_code == 422
    assert client.post(url, content=b"x" * 262145, headers=headers).status_code == 413
