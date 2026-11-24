import pytest

from studio_document_workflow import DocumentRequest, ApprovedRequest, preview, run
from studio_document_evidence import EvidenceRequest, evidence
from test_studio_document_extraction import txt, docx
from test_studio_document_search import document, approved, plan
from test_studio_multi_model import configured, AUTH


def inputs():
    p = plan()
    return DocumentRequest(documents=[
        {"id": d.id, "extraction": d.extraction} for d in p.documents],
        query=p.query, match=p.match, limit=p.limit)


def test_integrated_bundle_identical_to_existing_contract():
    p = inputs()
    checked = preview(p)
    assert "كتاب پژوهش" not in str(checked)
    a = ApprovedRequest(plan=p, review_sha256=checked["review_sha256"], consent=True)
    out = run(a)
    assert out == run(a)
    expected = evidence(EvidenceRequest(search=approved(plan()), include_excerpts=True))
    assert out["evidence"] == expected
    assert out["handoff"]["search_review_sha256"] == expected["search_review_sha256"]
    assert not out["provider_disclosure_authorized"] and not out["provider_contact_attempted"]
    assert "content_base64" not in str(out)


def test_stale_consent_duplicates_and_bounds():
    p = inputs()
    a = ApprovedRequest(plan=p, review_sha256=preview(p)["review_sha256"], consent=True)
    with pytest.raises(ValueError):
        run(a.model_copy(update={"consent": False}))
    with pytest.raises(ValueError):
        run(a.model_copy(update={"plan": p.model_copy(update={"query": "Other"})}))
    with pytest.raises(ValueError):
        preview(p.model_copy(update={"documents": [p.documents[0], p.documents[0]]}))
    clone = p.documents[0].model_copy(update={"id": "other"})
    with pytest.raises(ValueError):
        preview(p.model_copy(update={"documents": [p.documents[0], clone]}))


def test_docx_preserves_exclusion_and_no_match():
    p = DocumentRequest(documents=[{"id": "word", "extraction": docx(True)}], query="secret")
    out = run(ApprovedRequest(plan=p, review_sha256=preview(p)["review_sha256"], consent=True))
    assert out["status"] == "no_lexical_match"
    assert out["evidence"]["sources"] == []
    p = p.model_copy(update={"query": "table cell"})
    out = run(ApprovedRequest(plan=p, review_sha256=preview(p)["review_sha256"], consent=True))
    assert out["evidence"]["sources"][0]["location"]["row"] == 0


def test_one_inspection_per_file(monkeypatch):
    import studio_document_workflow as workflow
    original = workflow.inspect
    calls = []
    def counted(p):
        calls.append(p)
        return original(p)
    monkeypatch.setattr(workflow, "inspect", counted)
    p = inputs()
    checked = preview(p)
    assert len(calls) == 2
    calls.clear()
    run(ApprovedRequest(plan=p, review_sha256=checked["review_sha256"], consent=True))
    assert len(calls) == 2


def test_api_auth_and_no_model_budget(monkeypatch):
    with configured(monkeypatch, lambda _: pytest.fail("Unexpected provider call")) as client:
        url = "/studio/api/documents/workflow/"
        p = inputs().model_dump()
        assert client.post(url+"review", json=p).status_code == 401
        response = client.post(url+"review", json=p, headers=AUTH)
        assert response.status_code == 200, response.text
        checked = response.json()
        data = {"plan": p, "review_sha256": checked["review_sha256"], "consent": True}
        response = client.post(url+"run", json=data, headers=AUTH)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["evidence"]["source_count"] == 2
        assert client.post(url+"run", json={**data, "consent": False}, headers=AUTH).status_code == 422
        assert client.post(url+"run", content=b"x"*(3*1024*1024+1), headers=AUTH).status_code == 413
        assert client.app.state.model_budget.snapshot()["attempted"] == 0
