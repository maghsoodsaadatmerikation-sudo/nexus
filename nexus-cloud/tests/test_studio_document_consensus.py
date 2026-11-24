import json

import httpx

from test_studio_document_critique import plan, review, run, answer
from test_studio_multi_model import configured, AUTH, chat_answer, claude_answer, set_secondary


URL = "/studio/api/documents/critique/comparison"


def test_compare_two_adapters_without_additional_provider_attempt(monkeypatch):
    calls = []
    def handler(request):
        calls.append(request)
        secondary = request.url.host == "api.anthropic.com"
        result = answer(request, "contradicted" if secondary else "supported")
        content = json.dumps(result)
        return httpx.Response(200, json=claude_answer(content) if secondary else chat_answer(content))
    with configured(monkeypatch, handler) as client:
        set_secondary(monkeypatch)
        first = plan()
        second = plan()
        second["context"]["model_slot"] = "secondary"
        receipts = []
        for p in (first, second):
            response = run(client, p, review(client, p))
            assert response.status_code == 200, response.text
            receipts.append(response.json()["critique_receipt"])
        assert receipts[0]["context_id"] == receipts[1]["context_id"]
        assert len(calls) == 2
        data = {"receipts": receipts}
        assert client.post(URL, json=data).status_code == 401
        response = client.post(URL, json=data, headers=AUTH)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        out = response.json()
        assert out["disagreement_count"] == 2
        assert all(row["opposing_verdict_present"] for row in out["comparisons"])
        assert not out["truth_verified"] and not out["provider_contact_attempted"]
        assert len(calls) == 2 and client.app.state.model_budget.snapshot()["attempted"] == 2
        tampered = json.loads(json.dumps(data))
        tampered["receipts"][1]["votes"][0]["verdict"] = "supported"
        assert client.post(URL, json=tampered, headers=AUTH).status_code == 422
        assert client.post(URL, json={"receipts": [receipts[0], receipts[0]]}, headers=AUTH).status_code == 422
        assert client.post(URL, content=b"x"*16385, headers=AUTH).status_code == 413


def test_unanimity_and_context_mismatch(monkeypatch):
    def handler(request):
        content = json.dumps(answer(request))
        return httpx.Response(200, json=claude_answer(content) if request.url.host == "api.anthropic.com"
                              else chat_answer(content))
    with configured(monkeypatch, handler) as client:
        set_secondary(monkeypatch)
        first, second = plan(), plan()
        second["context"]["model_slot"] = "secondary"
        a = run(client, first, review(client, first)).json()["critique_receipt"]
        b = run(client, second, review(client, second)).json()["critique_receipt"]
        out = client.post(URL, json={"receipts": [a, b]}, headers=AUTH).json()
        assert out["disagreement_count"] == 0
        assert all(row["unanimous_verdict"] == "supported" for row in out["comparisons"])
        assert not out["semantic_agreement_verified"] and not out["independent_provenance_verified"]
        second["context"]["question"] = "A different question"
        c = run(client, second, review(client, second)).json()["critique_receipt"]
        assert client.post(URL, json={"receipts": [a, c]}, headers=AUTH).status_code == 422
