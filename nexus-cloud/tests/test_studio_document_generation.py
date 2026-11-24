import json

import httpx
import pytest

from studio_document_evidence import EvidenceRequest, evidence
from test_studio_document_search import plan, approved
from test_studio_multi_model import configured, AUTH, SECRET_PRIMARY, chat_answer, set_secondary, claude_answer


def payload():
    req = EvidenceRequest(search=approved(plan()))
    out = evidence(req)
    return {"evidence": req.model_dump(), "evidence_sha256": out["evidence_sha256"],
            "selected_evidence_ids": [out["sources"][0]["evidence_id"]],
            "question": "What is mentioned in the selected document?"}


def review(client, p):
    response = client.post("/studio/api/documents/generation/review", json=p, headers=AUTH)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def run(client, p, rid, consent=True):
    return client.post("/studio/api/documents/generation/run", headers=AUTH,
                       json={"plan": p, "request_review_id": rid, "provider_consent": consent})


def reply_for(body):
    user = json.loads(body["messages"][-1]["content"])
    source = user["untrusted_excerpts"][0]
    return {"status": "answer", "statements": [{
        "kind": "quotation", "text": source["excerpt"],
        "citations": [{"evidence_id": source["evidence_id"], "quote": source["excerpt"]}]}]}


def test_review_no_call_and_exact_selected_payload(monkeypatch):
    seen = []
    def handler(request):
        body = json.loads(request.content)
        seen.append(body)
        assert request.headers["authorization"] == "Bearer " + SECRET_PRIMARY
        user = json.loads(body["messages"][-1]["content"])
        assert len(user["untrusted_excerpts"]) == 1
        assert user["untrusted_excerpts"][0]["excerpt"] == "كتاب پژوهش"
        assert "کتاب و پژوهش" not in str(body)
        assert "content_base64" not in str(body)
        return httpx.Response(200, json=chat_answer(json.dumps(reply_for(body))))
    with configured(monkeypatch, handler) as client:
        p = payload()
        assert client.post("/studio/api/documents/generation/review", json=p).status_code == 401
        checked = review(client, p)
        assert not checked["provider_contact_attempted"] and not seen
        assert client.app.state.model_budget.snapshot()["attempted"] == 0
        assert run(client, p, checked["request_review_id"], False).status_code == 422
        assert run(client, {**p, "question": "Changed"}, checked["request_review_id"]).status_code == 409
        assert not seen
        response = run(client, p, checked["request_review_id"])
        assert response.status_code == 200, response.text
        out = response.json()
        assert out["status"] == "answer_with_checked_citations"
        row = out["statements"][0]
        assert row["exact_quotation_verified"] and not row["semantic_support_verified"]
        assert row["citations"][0]["location"] == {"line": 1}
        assert not out["semantic_verification"]
        assert client.app.state.model_budget.snapshot()["attempted"] == 1


@pytest.mark.parametrize("bad", ["unknown", "quote", "empty", "interpretation_no_citation",
                                  "duplicate_key", "truncated", "extra_field", "wrong_text"])
def test_invalid_output_fails_without_raw_leak_or_retry(monkeypatch, bad):
    calls = []
    def handler(request):
        calls.append(request)
        out = reply_for(json.loads(request.content))
        row = out["statements"][0]
        if bad == "unknown":
            row["citations"][0]["evidence_id"] = "e-" + "0"*64
        elif bad == "quote":
            row["citations"][0]["quote"] = "fabricated private output"
        elif bad == "empty":
            out["statements"] = []
        elif bad == "interpretation_no_citation":
            row["kind"] = "interpretation"
            row["citations"] = []
        elif bad == "extra_field":
            row["extra"] = "private"
        elif bad == "wrong_text":
            row["text"] = "fabricated private output"
        content = json.dumps(out)
        if bad == "duplicate_key":
            content = '{"status":"answer","status":"insufficient_evidence","statements":[]}'
        response = chat_answer(content)
        if bad == "truncated":
            response["choices"][0]["finish_reason"] = "length"
        return httpx.Response(200, json=response)
    with configured(monkeypatch, handler) as client:
        p = payload()
        checked = review(client, p)
        response = run(client, p, checked["request_review_id"])
        assert response.status_code == 502
        assert "fabricated private output" not in response.text
        assert len(calls) == 1
        assert client.app.state.model_budget.snapshot()["attempted"] == 1


def test_anthropic_interpretation_is_unverified(monkeypatch):
    def handler(request):
        body = json.loads(request.content)
        out = reply_for(body)
        out["statements"][0]["kind"] = "interpretation"
        out["statements"][0]["text"] = "An interpretation."
        return httpx.Response(200, json=claude_answer(json.dumps(out)))
    with configured(monkeypatch, handler) as client:
        set_secondary(monkeypatch)
        p = {**payload(), "model_slot": "secondary"}
        checked = review(client, p)
        response = run(client, p, checked["request_review_id"])
        assert response.status_code == 200, response.text
        row = response.json()["statements"][0]
        assert row["kind"] == "interpretation"
        assert not row["semantic_support_verified"] and not row["exact_quotation_verified"]


def test_abstention_and_unknown_selection(monkeypatch):
    def handler(_):
        return httpx.Response(200, json=chat_answer('{"status":"insufficient_evidence","statements":[]}'))
    with configured(monkeypatch, handler) as client:
        p = payload()
        assert client.post("/studio/api/documents/generation/review",
                           json={**p, "selected_evidence_ids": ["e-"+"0"*64]}, headers=AUTH).status_code == 422
        checked = review(client, p)
        out = run(client, p, checked["request_review_id"]).json()
        assert out["status"] == "insufficient_evidence" and out["statements"] == []
