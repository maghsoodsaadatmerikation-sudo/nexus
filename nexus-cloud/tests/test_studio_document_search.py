import hashlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_document_extraction import preview as extract_preview
from studio_document_search import ApprovedSearch, SearchPlan, preview, run, register
from test_studio_document_extraction import txt, docx


def document(id, plan):
    return {"id": id, "extraction": plan.model_dump(),
            "extraction_review_sha256": extract_preview(plan)["review_sha256"]}


def plan(**updates):
    return SearchPlan.model_validate({
        "documents": [document("first", txt("سلام\nكتاب پژوهش\nOther")),
                      document("second", txt("کتاب و پژوهش\nکتاب"))],
        "query": "کتاب پژوهش", **updates})


def approved(p):
    return ApprovedSearch(plan=p, review_sha256=preview(p)["review_sha256"], consent=True)


def test_multidocument_search_preserves_exact_persian_excerpt_and_location():
    p = plan()
    review = preview(p)
    assert "كتاب پژوهش" not in str(review)
    result = run(approved(p))
    assert result == run(approved(p))
    assert [r["document_id"] for r in result["hits"]] == ["first", "second"]
    assert result["hits"][0]["excerpt"] == "كتاب پژوهش"
    assert result["hits"][0]["location"] == {"line": 1}
    assert result["hits"][0]["excerpt_sha256"] == hashlib.sha256("كتاب پژوهش".encode()).hexdigest()
    assert result["hits"][0]["matched_query_tokens"] == ["پژوهش", "کتاب"]
    assert not result["answer_generated"] and not result["semantic_verification"]


def test_any_all_limit_and_no_match():
    result = run(approved(plan(match="any", limit=1)))
    assert result["matching_block_count"] == 3 and result["truncated"]
    assert len(result["hits"]) == 1
    result = run(approved(plan(query="unmatched")))
    assert result["status"] == "no_lexical_match" and not result["hits"]


def test_long_block_excerpt_exact_and_no_partial_tokens():
    text = "x"*1000 + " target needle " + "y"*1000
    p = plan(documents=[document("long", txt(text))], query="target needle")
    hit = run(approved(p))["hits"][0]
    assert hit["excerpt"] == text[hit["excerpt_start"]:hit["excerpt_end"]]
    assert len(hit["excerpt"]) <= 800
    assert not run(approved(plan(documents=[document("long", txt("a"*1000))],
                                 query="a")))["hits"]


def test_docx_reuses_extraction_exclusions():
    p = plan(documents=[document("word", docx(True))], query="secret")
    assert not run(approved(p))["hits"]
    p = plan(documents=[document("word", docx(True))], query="table cell")
    assert run(approved(p))["hits"][0]["location"]["row"] == 0


def test_reject_stale_duplicate_invalid_and_unapproved():
    p = plan()
    data = p.model_dump()
    data["documents"][0]["extraction_review_sha256"] = "0"*64
    with pytest.raises(ValueError):
        preview(SearchPlan.model_validate(data))
    with pytest.raises(ValueError):
        preview(plan(documents=[document("a", txt("same")), document("b", txt("same"))]))
    with pytest.raises(ValueError):
        preview(plan(query="---"))
    a = approved(p)
    with pytest.raises(ValueError):
        run(a.model_copy(update={"consent": False}))
    with pytest.raises(ValueError):
        run(a.model_copy(update={"plan": plan(query="Other")}))


def test_endpoint_auth_no_store_and_bounds(monkeypatch):
    token = "test-token-" + "x"*40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/documents/search/"
    headers = {"Authorization": "Bearer " + token}
    data = approved(plan()).model_dump()
    assert client.post(url+"review", json=data["plan"]).status_code == 401
    response = client.post(url+"review", json=data["plan"], headers=headers)
    assert response.status_code == 200
    assert response.json()["review_sha256"] == data["review_sha256"]
    response = client.post(url+"run", json=data, headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert client.post(url+"run", json={**data, "consent": "true"}, headers=headers).status_code == 422
    assert client.post(url+"run", content=b"x"*(3*1024*1024+1), headers=headers).status_code == 413
