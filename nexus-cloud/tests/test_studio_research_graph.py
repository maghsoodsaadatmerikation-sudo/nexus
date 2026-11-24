import copy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_research_evidence import EvidenceRequest, review
from studio_research_graph import GraphRequest, graph, register
from test_studio_research_reasoning import request_data


def payload():
    first = request_data()
    second = copy.deepcopy(first)
    second["evidence"]["claim"] = "Another test claim"
    second["evidence"]["assessments"][0]["stance"] = "challenges"
    second["review_sha256"] = review(
        EvidenceRequest.model_validate(second["evidence"]))["review_sha256"]
    return {"concepts": [{"id": "topic", "label": "Shared topic"}], "claims": [
        {"id": "first", "reasoning": first, "concept_ids": ["topic"]},
        {"id": "second", "reasoning": second, "concept_ids": ["topic"]},
    ]}


def result(data):
    return graph(GraphRequest.model_validate(data))


def test_shared_sources_do_not_propagate_stance():
    data = payload()
    out = result(data)
    assert out == result(data)
    assert out["claim_count"] == 2
    assert out["distinct_source_identities"] == 2
    assert len(out["shared_source_ids"]) == 2
    assert len(out["nodes"]) == 5 and len(out["edges"]) == 6
    source = next(node for node in out["nodes"] if node.get("identity") == "doi:10.1234/abc")
    edges = [edge for edge in out["edges"] if edge["from"] == source["id"]]
    assert {edge["to"]: edge["relation"] for edge in edges} == {
        "claim:first": "caller_reported_supports",
        "claim:second": "caller_reported_challenges",
    }
    assert edges[0]["method_annotations"][0]["excerpt_sha256"]
    assert all(edge["evidence_review_sha256"] for edge in edges)
    assert out["semantic_inference"] is False
    assert out["independent_verification"] is False
    assert out["execution_authorized"] is False
    assert "Unverified excerpt" not in str(out)


@pytest.mark.parametrize("change", ["claim", "concept", "unknown", "duplicate_link", "stale"])
def test_invalid_graph(change):
    data = payload()
    if change == "claim":
        data["claims"][1]["id"] = "first"
    elif change == "concept":
        data["concepts"].append(copy.deepcopy(data["concepts"][0]))
    elif change == "unknown":
        data["claims"][0]["concept_ids"] = ["missing"]
    elif change == "duplicate_link":
        data["claims"][0]["concept_ids"] = ["topic", "topic"]
    else:
        data["claims"][0]["reasoning"]["evidence"]["claim"] = "Changed"
    with pytest.raises(ValueError):
        result(data)


def test_global_card_budget():
    data = payload()
    for claim in data["claims"]:
        cards = claim["reasoning"]["evidence"]["cards"]
        cards.extend([copy.deepcopy(cards[0]) for _ in range(28)])
    with pytest.raises(ValueError, match="budget"):
        result(data)


def test_graph_digest_binds_concept_label():
    data = payload()
    first = result(data)
    data["concepts"][0]["label"] = "Updated topic"
    second = result(data)
    assert first["graph_sha256"] != second["graph_sha256"]
    assert first["shared_source_ids"] == second["shared_source_ids"]


def test_endpoint_auth_and_bounds(monkeypatch):
    token = "test-token-" + "x" * 40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/research/knowledge-graph"
    headers = {"Authorization": "Bearer " + token}
    assert client.post(url, json=payload()).status_code == 401
    response = client.post(url, json=payload(), headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["distinct_source_identities"] == 2
    data = payload()
    data["claims"][0]["concept_ids"] = ["missing"]
    assert client.post(url, json=data, headers=headers).status_code == 422
    assert client.post(url, content=b"x" * 262145, headers=headers).status_code == 413
