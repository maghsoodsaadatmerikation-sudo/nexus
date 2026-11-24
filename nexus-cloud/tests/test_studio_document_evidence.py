import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_document_evidence import EvidenceRequest, AuditRequest, evidence, audit, register
from test_studio_document_search import plan, approved


def request(**options):
    return EvidenceRequest(search=approved(plan()), **options)


def payload():
    req = request(include_excerpts=True)
    out = evidence(req)
    first = out["sources"][0]
    quote = first["excerpt"]
    return {"evidence": req.model_dump(), "evidence_sha256": out["evidence_sha256"],
            "statements": [{"kind": "quotation", "text": quote,
                            "citations": [{"evidence_id": first["evidence_id"],
                                           "start": 0, "end": len(quote), "quote": quote}]}]}


def result(data):
    return audit(AuditRequest.model_validate(data))


def test_evidence_recomputed_and_opt_in_text():
    private = evidence(request())
    visible = evidence(request(include_excerpts=True))
    assert private["evidence_sha256"] == visible["evidence_sha256"]
    assert private["source_count"] == 2
    assert all("excerpt" not in row for row in private["sources"])
    assert visible["sources"][0]["excerpt"] == "كتاب پژوهش"
    assert not visible["model_called"] and not visible["semantic_verification"]


def test_exact_quotation_and_interpretation_distinguished():
    data = payload()
    out = result(data)
    assert out == result(data)
    assert out["status"] == "exact_quotations_matched"
    assert out["statements"][0]["exact_quotation_verified"]
    assert not out["statements"][0]["semantic_support_verified"]
    data["statements"][0]["kind"] = "interpretation"
    out = result(data)
    assert out["status"] == "review_required"
    assert out["findings"] == [{"statement_index": 0, "code": "interpretation_requires_semantic_review"}]


@pytest.mark.parametrize("bad,code", [
    ("unknown", "unknown_evidence_id"), ("quote", "quote_mismatch"),
    ("span", "invalid_excerpt_span"), ("text", "statement_not_exact_quotation"),
    ("missing", "missing_citation"), ("duplicate", "duplicate_citation_span"),
])
def test_unverified_citations_flagged(bad, code):
    data = payload()
    statement = data["statements"][0]
    cite = statement["citations"][0]
    if bad == "unknown":
        cite["evidence_id"] = "e-" + "0"*64
    elif bad == "quote":
        cite["quote"] = "fabricated"
    elif bad == "span":
        cite["end"] = 800
    elif bad == "text":
        statement["text"] += " invented conclusion"
    elif bad == "missing":
        statement["citations"] = []
    else:
        statement["citations"].append(dict(cite))
    out = result(data)
    assert code in {f["code"] for f in out["findings"]}
    assert not out["statements"][0]["exact_quotation_verified"]


def test_stale_digest_and_no_consent():
    data = payload()
    data["evidence_sha256"] = "0"*64
    with pytest.raises(ValueError):
        result(data)
    data = payload()
    data["evidence"]["search"]["consent"] = False
    with pytest.raises(ValueError):
        result(data)


def test_no_matching_evidence():
    out = evidence(EvidenceRequest(search=approved(plan(query="nonexistent")), include_excerpts=True))
    assert out["status"] == "no_lexical_match" and out["sources"] == []


def test_endpoint_auth_and_bounds(monkeypatch):
    token = "test-token-" + "x"*40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    headers = {"Authorization": "Bearer " + token}
    url = "/studio/api/documents/"
    assert client.post(url+"evidence", json=request().model_dump()).status_code == 401
    response = client.post(url+"evidence", json=request().model_dump(), headers=headers)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    response = client.post(url+"answer-audit", json=payload(), headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "exact_quotations_matched"
    assert client.post(url+"answer-audit", content=b"x"*(3*1024*1024+1), headers=headers).status_code == 413
