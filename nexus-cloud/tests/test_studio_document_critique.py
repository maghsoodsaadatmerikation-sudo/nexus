import json

import httpx
import pytest

from test_studio_document_generation import payload
from test_studio_multi_model import configured, AUTH, chat_answer


def plan():
    context = payload()
    quote = "كتاب پژوهش"
    citation = {"evidence_id": context["selected_evidence_ids"][0], "quote": quote}
    return {"context": context, "draft": {"status": "answer", "statements": [
        {"kind": "quotation", "text": quote, "citations": [citation]},
        {"kind": "interpretation", "text": "An inference", "citations": [citation]},
    ]}}


def review(client, data):
    resp = client.post("/studio/api/documents/critique/review", json=data, headers=AUTH)
    assert resp.status_code == 200, resp.text
    return resp.json()["request_review_id"]


def run(client, data, rid, consent=True):
    return client.post("/studio/api/documents/critique/run", headers=AUTH,
                       json={"plan": data, "request_review_id": rid, "provider_consent": consent})


def answer(request, verdict="supported"):
    user = json.loads(json.loads(request.content)["messages"][-1]["content"])
    citation = user["untrusted_draft"]["statements"][0]["citations"][0]
    return {"assessments": [
        {"statement_index": i, "verdict": verdict, "rationale": "Model assessment.",
         "citations": [citation]} for i in range(2)
    ]}


def test_review_and_conservative_filter(monkeypatch):
    calls = []
    def handler(request):
        calls.append(request)
        assert "content_base64" not in request.content.decode()
        return httpx.Response(200, json=chat_answer(json.dumps(answer(request))))
    with configured(monkeypatch, handler) as client:
        data = plan()
        assert client.post("/studio/api/documents/critique/review", json=data).status_code == 401
        rid = review(client, data)
        assert not calls and client.app.state.model_budget.snapshot()["attempted"] == 0
        assert run(client, data, rid, False).status_code == 422
        changed = plan()
        changed["draft"]["statements"][1]["text"] = "Changed inference"
        assert run(client, changed, rid).status_code == 409
        assert not calls
        response = run(client, data, rid)
        assert response.status_code == 200, response.text
        out = response.json()
        assert [row["statement_index"] for row in out["conservative_extractive_candidate"]] == [0]
        assert out["withheld_statement_indices"] == [1]
        assert not out["semantic_verification"] and not out["automatic_rewrite_performed"]
        assert len(calls) == 1 and client.app.state.model_budget.snapshot()["attempted"] == 1


@pytest.mark.parametrize("bad", ["missing", "duplicate", "unknown", "fabricated", "no_citations"])
def test_invalid_critique_fails_closed(monkeypatch, bad):
    calls = []
    def handler(request):
        calls.append(request)
        out = answer(request)
        rows = out["assessments"]
        if bad == "missing":
            rows.pop()
        elif bad == "duplicate":
            rows[1]["statement_index"] = 0
        elif bad == "unknown":
            rows[0]["citations"][0]["evidence_id"] = "e-"+"0"*64
        elif bad == "fabricated":
            rows[0]["citations"][0]["quote"] = "fabricated secret"
        else:
            rows[0]["citations"] = []
        return httpx.Response(200, json=chat_answer(json.dumps(out)))
    with configured(monkeypatch, handler) as client:
        data = plan()
        response = run(client, data, review(client, data))
        assert response.status_code == 502
        assert "fabricated secret" not in response.text and len(calls) == 1


def test_disputed_quotations_withheld(monkeypatch):
    def handler(request):
        return httpx.Response(200, json=chat_answer(json.dumps(answer(request, "contradicted"))))
    with configured(monkeypatch, handler) as client:
        data = plan()
        out = run(client, data, review(client, data)).json()
        assert out["conservative_extractive_candidate"] == []
        assert out["withheld_statement_indices"] == [0, 1]
