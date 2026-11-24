import hashlib
import html
import json
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_research_export import ExportRequest, build_export, register, render_html
from studio_research_synthesis import SynthesisRequest, synthesize
from test_studio_research_synthesis import payload as synthesis_data


def payload(format="html"):
    data = synthesis_data()
    report = synthesize(SynthesisRequest.model_validate(data))
    return {"synthesis": data, "report_sha256": report["report_sha256"],
            "format": format, "export_consent": True}


def result(data):
    return build_export(ExportRequest.model_validate(data))


def test_json_export_preserves_entire_review():
    data = payload("json")
    raw, media = result(data)
    assert media == "application/json"
    assert json.loads(raw) == synthesize(SynthesisRequest.model_validate(data["synthesis"]))
    assert raw == result(data)[0]
    assert b"Unverified excerpt" not in raw and b"A test claim" not in raw


def test_html_preserves_report_and_human_review_warnings():
    data = payload()
    raw, media = result(data)
    assert media == "text/html"
    page = raw.decode("utf-8")
    assert "Human review required" in page
    assert "potential_conflict_requires_review" in page
    assert "References — incomplete and unverified" in page
    assert "Unresolved uncertainties" in page
    assert data["report_sha256"] in page
    assert "<script" not in page and "Unverified excerpt" not in page
    extracted = re.search(r"<pre>(.*?)</pre>", page, re.S).group(1)
    assert json.loads(html.unescape(extracted)) == synthesize(
        SynthesisRequest.model_validate(data["synthesis"]))
    assert raw == result(data)[0]


def test_render_escapes_untrusted_claim_and_reference_text():
    data = payload()
    report = synthesize(SynthesisRequest.model_validate(data["synthesis"]))
    report["claims"][0]["caller_supplied_claim"] = '<img src=x onerror="alert(1)">'
    report["references"][0]["title"] = "</pre><script>alert(2)</script>"
    page = render_html(report).decode("utf-8")
    assert "<img src=" not in page and "<script>" not in page
    assert "&lt;img src=x" in page and "&lt;script&gt;" in page


@pytest.mark.parametrize("change", ["consent", "stale", "changed_disclosure", "damaged", "format"])
def test_invalid_export(change):
    data = payload()
    if change == "consent":
        data["export_consent"] = False
    elif change == "stale":
        data["report_sha256"] = "0" * 64
    elif change == "changed_disclosure":
        data["synthesis"]["include_claim_text"] = True
    elif change == "damaged":
        data["synthesis"]["review"]["candidate"]["unresolved_item_ids"].pop()
    else:
        data["format"] = "exe"
    with pytest.raises(ValueError):
        result(data)


def test_endpoint_auth_and_attachment_headers(monkeypatch):
    token = "test-token-" + "x" * 40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/research/export"
    headers = {"Authorization": "Bearer " + token}
    data = payload()
    assert client.post(url, json=data).status_code == 401
    response = client.post(url, json=data, headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-disposition"] == 'attachment; filename="nexus-research-draft.html"'
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-nexus-content-sha256"] == hashlib.sha256(response.content).hexdigest()
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert client.post(url, json={**data, "export_consent": "true"}, headers=headers).status_code == 422
    assert client.post(url, content=b"x" * 393217, headers=headers).status_code == 413
