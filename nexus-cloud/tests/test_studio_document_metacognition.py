import json

import httpx

from test_studio_document_critique import plan, review, run, answer
from test_studio_multi_model import configured, AUTH, chat_answer, claude_answer, set_secondary

URL = "/studio/api/documents/metacognition"


def test_no_critique_still_exposes_uncertainty(monkeypatch):
    def handler(_):
        raise AssertionError("Unexpected provider call")
    with configured(monkeypatch, handler) as client:
        p = {"plan": plan()}
        assert client.post(URL, json=p).status_code == 401
        resp = client.post(URL, json=p, headers=AUTH)
        assert resp.status_code == 200, resp.text
        assert resp.headers["cache-control"] == "no-store"
        out = resp.json()
        assert out == client.post(URL, json=p, headers=AUTH).json()
        assert out["reviewer_count"] == 0
        assert {"no_model_critique", "some_retrieved_excerpts_not_selected",
                "interpretation_unverified"} <= {a["code"] for a in out["review_actions"]}
        assert out["statement_inventory"][1]["disposition"] == "withhold_pending_review"
        assert not out["confidence_estimated"] and not out["truth_verified"]
        assert client.app.state.model_budget.snapshot()["attempted"] == 0


def test_receipts_bind_exact_context_and_preserve_disagreement(monkeypatch):
    calls = []
    def handler(request):
        calls.append(request)
        secondary = request.url.host == "api.anthropic.com"
        content = json.dumps(answer(request, "mixed" if secondary else "supported"))
        return httpx.Response(200, json=claude_answer(content) if secondary else chat_answer(content))
    with configured(monkeypatch, handler) as client:
        set_secondary(monkeypatch)
        p, q = plan(), plan()
        q["context"]["model_slot"] = "secondary"
        receipts = [run(client, x, review(client, x)).json()["critique_receipt"] for x in (p, q)]
        data = {"plan": p, "receipts": receipts}
        resp = client.post(URL, json=data, headers=AUTH)
        assert resp.status_code == 200, resp.text
        out = resp.json()
        assert out["reviewer_count"] == 2
        assert {"model_disagreement", "opposition_reported", "reviewer_independence_unverified"} <= {
            a["code"] for a in out["review_actions"]}
        assert all(s["disposition"] == "withhold_pending_review" for s in out["statement_inventory"])
        assert not out["provider_contact_attempted"] and len(calls) == 2
        changed = json.loads(json.dumps(data))
        changed["plan"]["context"]["question"] = "Different question"
        assert client.post(URL, json=changed, headers=AUTH).status_code == 422
        changed = json.loads(json.dumps(data))
        changed["receipts"][0]["votes"][0]["verdict"] = "insufficient"
        assert client.post(URL, json=changed, headers=AUTH).status_code == 422
        assert client.post(URL, json={"plan": p, "receipts": [receipts[0], receipts[0]]},
                           headers=AUTH).status_code == 422
        assert len(calls) == 2


def test_single_supported_critique_does_not_promote_interpretation(monkeypatch):
    def handler(req):
        return httpx.Response(200, json=chat_answer(json.dumps(answer(req))))
    with configured(monkeypatch, handler) as client:
        p = plan()
        receipt = run(client, p, review(client, p)).json()["critique_receipt"]
        out = client.post(URL, json={"plan": p, "receipts": [receipt]}, headers=AUTH).json()
        assert out["reviewer_count"] == 1
        assert out["statement_inventory"][0]["disposition"] == "exact_quote_candidate_requires_context_review"
        assert out["statement_inventory"][1]["disposition"] == "withhold_pending_review"
        assert "single_model_critique" in {a["code"] for a in out["review_actions"]}
        assert not out["automatic_correction_performed"]
        assert client.post(URL, content=b"x"*(3*1024*1024+1), headers=AUTH).status_code == 413
