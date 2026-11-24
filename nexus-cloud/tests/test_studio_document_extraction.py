import base64
import hashlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_document_extraction import ExtractionPlan, ApprovedExtraction, preview, run, register
from studio_document_privacy import W
from test_studio_document_privacy import fixture


def txt(text):
    return ExtractionPlan(format="txt", content_base64=base64.b64encode(text.encode()).decode())


def approved(plan):
    return ApprovedExtraction(plan=plan, review_sha256=preview(plan)["review_sha256"], consent=True)


def docx(tables=False):
    body = (
        '<w:p><w:r><w:t>Public text</w:t></w:r><w:r><w:tab/><w:t>Second</w:t></w:r></w:p>'
        '<w:p><w:r><w:rPr><w:vanish/></w:rPr><w:t>Hidden secret</w:t></w:r></w:p>'
        '<w:p><w:del><w:r><w:delText>Deleted secret</w:delText></w:r></w:del></w:p>'
        '<w:p><w:r><w:fldChar w:fldCharType="begin"/><w:t>Field secret</w:t></w:r></w:p>'
        '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Table cell</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
    )
    original = fixture({"word/document.xml": f'<w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>'})
    return ExtractionPlan(format="docx", content_base64=original.docx_base64, include_table_cells=tables)


def test_text_review_does_not_expose_text_and_run_preserves_lines():
    plan = txt("سلام\n\nSecond line")
    out = preview(plan)
    assert "سلام" not in str(out) and "Second line" not in str(out)
    assert out["block_count"] == 2
    result = run(approved(plan))
    assert result == run(approved(plan))
    assert [b["text"] for b in result["blocks"]] == ["سلام", "Second line"]
    assert result["blocks"][1]["location"] == {"line": 2}
    assert result["blocks"][0]["sha256"] == hashlib.sha256("سلام".encode()).hexdigest()
    assert not result["complete_extraction_verified"]


def test_docx_skips_explicit_sensitive_markup_and_respects_table_option():
    result = run(approved(docx()))
    assert [b["text"] for b in result["blocks"]] == ["Public text\tSecond"]
    assert result["skipped_counts"]["paragraph_with_field_revision_or_hidden_marker"] == 3
    assert result["skipped_counts"]["table_not_requested"] == 1
    assert "secret" not in str(result)
    assert not result["anonymity_verified"]
    result = run(approved(docx(True)))
    assert result["blocks"][1]["text"] == "Table cell"
    assert result["blocks"][1]["location"] == {"body_index": 4, "row": 0, "cell": 0, "cell_child": 0}


def test_consent_bounds_and_stale_plan():
    data = approved(txt("Hello"))
    with pytest.raises(ValueError):
        run(data.model_copy(update={"consent": False}))
    with pytest.raises(ValueError):
        run(data.model_copy(update={"plan": txt("Different")}))
    for invalid in (txt("   "), txt("bad\x00"), txt("x\n"*2001), txt("x"*200001)):
        with pytest.raises(ValueError):
            preview(invalid)
    with pytest.raises(ValueError):
        preview(txt("hello").model_copy(update={"include_table_cells": True}))


def test_auth_no_store_and_bounds(monkeypatch):
    token = "test-token-" + "x"*40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/documents/extraction/"
    headers = {"Authorization": "Bearer " + token}
    data = approved(txt("Hello")).model_dump()
    assert client.post(url+"review", json=data["plan"]).status_code == 401
    response = client.post(url+"review", json=data["plan"], headers=headers)
    assert response.status_code == 200
    assert response.json()["review_sha256"] == data["review_sha256"]
    response = client.post(url+"run", json=data, headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["blocks"][0]["text"] == "Hello"
    assert client.post(url+"run", json={**data, "consent": "true"}, headers=headers).status_code == 422
    assert client.post(url+"review", json={"format": "txt", "content_base64": "!!!!"}, headers=headers).status_code == 422
    assert client.post(url+"run", content=b"x"*(3*1024*1024+1), headers=headers).status_code == 413
