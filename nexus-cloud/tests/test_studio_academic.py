import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_academic import ManuscriptRequest, review, register
from studio_research_synthesis import SynthesisRequest, synthesize
from test_studio_research_synthesis import payload as synthesis_data


def payload():
    data = synthesis_data()
    report = synthesize(SynthesisRequest.model_validate(data))
    return {"synthesis": data, "report_sha256": report["report_sha256"],
            "article_type": "commentary", "title": "A conceptual draft",
            "sections": [
                {"id": "introduction", "text": "Context and question."},
                {"id": "discussion", "text": "Caller supplied argument.",
                 "citations": [{"claim_id": row["claim_id"],
                                "references": [link["reference_number"]
                                               for link in row["reference_links"]]}
                               for row in report["claims"]]},
                {"id": "limitations", "text": "Evidence remains unverified."},
                {"id": "declarations", "text": "For author review."},
            ]}


def result(data):
    return review(ManuscriptRequest.model_validate(data))


def test_structural_review_preserves_uncertainty_without_submission_claim():
    data = payload()
    out = result(data)
    assert out == result(data)
    assert out["status"] == "structural_checks_passed"
    assert out["word_counts"]["title"] == 3
    assert out["word_counts"]["manuscript"] == 12
    assert out["unresolved_research_issues"]
    assert out["references"]
    assert out["human_review_required"]
    assert not out["citation_entailment_verified"]
    assert not out["journal_requirements_verified"]
    assert not out["submission_authorized"]
    assert "Caller supplied argument" not in str(out)


def test_missing_sections_claims_limits_and_opposing_evidence():
    data = payload()
    data["article_type"] = "empirical"
    data["sections"][1]["citations"].pop()
    data["sections"][1]["citations"][0]["references"] = [1]
    data["limits"] = {"title_words": 1}
    out = result(data)
    codes = {item["code"] for item in out["findings"]}
    assert out["status"] == "revision_required"
    assert {"missing_section", "unmapped_reviewed_claim", "word_limit_exceeded",
            "opposing_source_not_linked"} <= codes
    assert out["manuscript_review_sha256"] != result(payload())["manuscript_review_sha256"]


@pytest.mark.parametrize("bad", ["digest", "duplicate_section", "reference", "claim", "duplicate_reference"])
def test_invalid_mapping(bad):
    data = payload()
    if bad == "digest":
        data["report_sha256"] = "0" * 64
    elif bad == "duplicate_section":
        data["sections"].append(data["sections"][0])
    elif bad == "reference":
        data["sections"][1]["citations"][0]["references"] = [60]
    elif bad == "claim":
        data["sections"][1]["citations"][0]["claim_id"] = "claim:missing"
    else:
        data["sections"][1]["citations"][0]["references"] = [1, 1]
    with pytest.raises(ValueError):
        result(data)


def test_endpoint_auth_and_bounds(monkeypatch):
    token = "test-token-" + "x" * 40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/research/manuscript-review"
    headers = {"Authorization": "Bearer " + token}
    assert client.post(url, json=payload()).status_code == 401
    response = client.post(url, json=payload(), headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["submission_authorized"] is False
    assert client.post(url, content=b"x" * 786433, headers=headers).status_code == 413
