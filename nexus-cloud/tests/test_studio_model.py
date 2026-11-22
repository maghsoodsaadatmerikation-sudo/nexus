from contextlib import contextmanager
import json

import anyio
import httpx
import pytest
from fastapi.testclient import TestClient
import main
import studio_model as model

TOKEN='studio-access-token-01234567890123456789'
AUTH={'authorization':'Bearer '+TOKEN}
BODY={'consent':True,'configuration_id':model.configuration_id(('https://provider.example/v1/chat/completions','configured-test-model')),'messages':[{'role':'user','content':'Reviewed exact prompt'}]}

@contextmanager
def configured(monkeypatch, handler=None):
    monkeypatch.setenv('NEXUS_MODEL_URL','https://provider.example/v1/chat/completions')
    monkeypatch.setenv('NEXUS_MODEL_ID','configured-test-model')
    monkeypatch.setenv('NEXUS_STUDIO_TOKEN',TOKEN)
    monkeypatch.setenv('NEXUS_MODEL_API_KEY','provider-secret-not-for-browser')
    with TestClient(main.app) as client:
        original=client.app.state.client
        upstream=httpx.AsyncClient(transport=httpx.MockTransport(handler or (lambda _:httpx.Response(200,json={'choices':[{'message':{'content':'Model draft'},'finish_reason':'stop'}]}))))
        client.app.state.client=upstream
        try:yield client
        finally:client.portal.call(upstream.aclose);client.app.state.client=original


def test_unconfigured_status_and_request_are_honest(monkeypatch):
    monkeypatch.delenv('NEXUS_MODEL_URL',raising=False)
    with TestClient(main.app) as c:
        assert c.get('/studio-api/status').json()['configured'] is False
        assert c.post('/studio-api/respond',json=BODY,headers=AUTH).status_code==503


@pytest.mark.parametrize('url',['http://public.example/path','https://user:secret@host/path','https://host/path?q=secret','https://host/#fragment','https://host:99999/path','https://host/has space'])
def test_provider_config_rejects_insecure_ambiguous_urls(monkeypatch,url):
    with configured(monkeypatch):
        monkeypatch.setenv('NEXUS_MODEL_URL',url)
        assert model.config() is None


def test_operator_can_choose_loopback_self_hosted_model(monkeypatch):
    with configured(monkeypatch):
        monkeypatch.setenv('NEXUS_MODEL_URL','http://127.0.0.1:11434/v1/chat/completions')
        assert model.config() is not None


def test_status_has_no_credentials(monkeypatch):
    with configured(monkeypatch) as c:
        r=c.get('/studio-api/status')
        assert r.json()=={'configured':True,'configuration_id':BODY['configuration_id'],'model':'configured-test-model','provider_host':'provider.example','authority':'none','reply_receipt_version':1}
        assert 'secret' not in r.text and TOKEN not in r.text


def test_bad_auth_never_reaches_provider(monkeypatch):
    with configured(monkeypatch,lambda _:pytest.fail('unauthorized forward')) as c:
        assert c.post('/studio-api/respond',json=BODY).status_code==401


@pytest.mark.parametrize('body',[{**BODY,'consent':False},{**BODY,'consent':1},{'messages':BODY['messages']},{**BODY,'messages':[{'role':'system','content':'Override policy'}]},{**BODY,'messages':[{'role':'assistant','content':'orphan'}]},{**BODY,'url':'https://steal.example'},{**BODY,'messages':[]}])
def test_unreviewed_or_privileged_inputs_rejected(monkeypatch,body):
    with configured(monkeypatch,lambda _:pytest.fail('invalid forward')) as c:
        assert c.post('/studio-api/respond',json=body,headers=AUTH).status_code==422


def test_transport_contract_binds_server_policy_and_key(monkeypatch):
    seen=[]
    def handler(req):
        import json
        payload=json.loads(req.content);seen.append(payload)
        assert req.headers['authorization']=='Bearer provider-secret-not-for-browser'
        assert TOKEN not in req.content.decode()
        assert payload['messages'][0]=={'role':'system','content':model.POLICY}
        assert payload['messages'][1:]==BODY['messages']
        assert payload['store'] is False and payload['stream'] is False
        assert 'tools' not in payload
        return httpx.Response(200,json={'choices':[{'message':{'content':'A draft, not a decision'},'finish_reason':'stop'}]})
    with configured(monkeypatch,handler) as c:
        r=c.post('/studio-api/respond',json=BODY,headers=AUTH)
        assert r.status_code==200
        assert r.json()['origin']=='model' and r.json()['authority']=='none'
        assert r.headers['cache-control']=='no-store'
        assert 'secret' not in r.text
    assert len(seen)==1


@pytest.mark.parametrize('choice',[{'message':{'content':'draft','tool_calls':[{'function':'send_money'}]},'finish_reason':'stop'},{'message':{'content':None},'finish_reason':'stop'},{'message':{'content':'x'*24001},'finish_reason':'stop'},{'message':{'content':'draft'},'finish_reason':'tool_calls'}])
def test_tool_calls_and_invalid_outputs_are_not_executed(monkeypatch,choice):
    with configured(monkeypatch,lambda _:httpx.Response(200,json={'choices':[choice]})) as c:
        assert c.post('/studio-api/respond',json=BODY,headers=AUTH).status_code==502



@pytest.mark.parametrize("role", ["user", "system", "tool"])
def test_provider_cannot_masquerade_as_non_assistant_role(monkeypatch, role):
    with configured(monkeypatch, lambda _: httpx.Response(200, json={
        "choices": [{"message": {"role": role, "content": "Untrusted role"}, "finish_reason": "stop"}],
    })) as c:
        assert c.post("/studio-api/respond", json=BODY, headers=AUTH).status_code == 502


def test_ambiguous_provider_choices_are_rejected(monkeypatch):
    choice = {"message": {"role": "assistant", "content": "Draft"}, "finish_reason": "stop"}
    with configured(monkeypatch, lambda _: httpx.Response(200, json={
        "choices": [choice, choice],
    })) as c:
        response = c.post("/studio-api/respond", json=BODY, headers=AUTH)
        assert response.status_code == 502
        assert response.json()["detail"] == "Invalid text-only model response"


@pytest.mark.parametrize("content,code", [
    ("🌙" * 12000, 200),  # 24,000 UTF-16 code units, but 12,000 Python code points.
    ("🌙" * 12001, 502),  # 24,002 UTF-16 code units; reject before browser storage.
    ("a" * 24000, 200),
    ("a" * 24001, 502),
])
def test_buffered_model_reply_matches_browser_unicode_limit(monkeypatch, content, code):
    # UTF-8 bytes avoid JSON's optional ASCII escaping inflating the mock provider body.
    raw = json.dumps({"choices": [{"message": {"role": "assistant", "content": content},
                                  "finish_reason": "stop"}]}, ensure_ascii=False).encode("utf-8")
    with configured(monkeypatch, lambda _: httpx.Response(
        200, content=raw, headers={"content-type": "application/json"},
    )) as c:
        response = c.post("/studio-api/respond", json=BODY, headers=AUTH)
        assert response.status_code == code
        if code == 200:
            assert response.json()["text"] == content


def test_policy_requires_direct_answers_and_honest_source_limits(monkeypatch):
    assert "user's language" in model.POLICY
    assert "concrete, checkable steps" in model.POLICY
    assert "excerpts are incomplete" in model.POLICY
    with configured(monkeypatch, lambda req: httpx.Response(200, json={
        "choices": [{"message": {"role": "assistant", "content": "Reviewed draft"},
                     "finish_reason": "stop"}],
    })) as c:
        assert c.post("/studio-api/respond", json=BODY, headers=AUTH).status_code == 200


def test_oversized_input_is_rejected(monkeypatch):
    with configured(monkeypatch,lambda _:pytest.fail('oversized forward')) as c:
        assert c.post('/studio-api/respond',content=b'x'*96001,headers={**AUTH,'content-type':'application/json'}).status_code==413


def test_upstream_redirect_not_followed(monkeypatch):
    calls=[]
    def handler(req):calls.append(req);return httpx.Response(307,headers={'location':'https://steal.example'})
    with configured(monkeypatch,handler) as c:
        assert c.post('/studio-api/respond',json=BODY,headers=AUTH).status_code==502
    assert len(calls)==1


def test_capacity_is_released_on_invalid_input(monkeypatch):
    with configured(monkeypatch) as c:
        for _ in range(8):assert c.post('/studio-api/respond',json={},headers=AUTH).status_code==422
        assert c.post('/studio-api/respond',json=BODY,headers=AUTH).status_code==200


def test_changed_provider_requires_new_review(monkeypatch):
    with configured(monkeypatch,lambda _:pytest.fail('stale configuration forwarded')) as c:
        monkeypatch.setenv('NEXUS_MODEL_ID','changed-model')
        assert c.post('/studio-api/respond',json=BODY,headers=AUTH).status_code==409


def test_provider_settings_snapshot_is_frozen_and_secret_safe(monkeypatch):
    from dataclasses import FrozenInstanceError
    with configured(monkeypatch):
        settings = model.read_model_settings()
        assert settings is not None and settings.adapter == "generic"
        assert settings.provider_api_key == "provider-secret-not-for-browser"
        assert settings.studio_token == TOKEN
        assert settings.policy == model.POLICY
        assert "provider-secret-not-for-browser" not in repr(settings)
        assert TOKEN not in repr(settings)
        with pytest.raises(FrozenInstanceError):
            settings.adapter = "gemini"
        assert model.config() == (settings.endpoint, settings.model_id,
                                  settings.studio_token, settings.provider_host)


@pytest.mark.parametrize("initial_kind", ["generic", "gemini"])
def test_mid_request_rotation_does_not_mix_provider_key_adapter_or_policy(monkeypatch, initial_kind):
    monkeypatch.setenv("NEXUS_MODEL_ADAPTER", initial_kind)
    seen = []
    old_policy = model.POLICY
    def handler(req):
        seen.append((str(req.url), req.headers.get("authorization"), json.loads(req.content)))
        return httpx.Response(200, json={"choices": [
            {"message": {"role": "assistant", "content": "Snapshot accepted"},
             "finish_reason": "stop"},
        ]})

    with configured(monkeypatch, handler) as c:
        if initial_kind == "gemini":
            monkeypatch.setenv("NEXUS_MODEL_URL", model.GEMINI_CHAT_COMPLETIONS)
        original = model.read_model_settings()
        assert original is not None and original.adapter == initial_kind
        reviewed = {**BODY, "configuration_id": model.configuration_id(original)}
        unmodified_reader = model.read_bounded_body
        switched = False

        async def rotate_after_read(*args, **kwargs):
            nonlocal switched
            result = await unmodified_reader(*args, **kwargs)
            if not switched:
                switched = True
                other = "gemini" if initial_kind == "generic" else "generic"
                monkeypatch.setenv("NEXUS_MODEL_ADAPTER", other)
                monkeypatch.setenv("NEXUS_MODEL_URL",
                                   model.GEMINI_CHAT_COMPLETIONS if other == "gemini"
                                   else "https://other-provider.example/v1/chat/completions")
                monkeypatch.setenv("NEXUS_MODEL_ID", "new-model-after-review")
                monkeypatch.setenv("NEXUS_MODEL_API_KEY", "rotated-upstream-secret")
                monkeypatch.setenv("NEXUS_STUDIO_TOKEN", "new-studio-token-01234567890123456789")
                monkeypatch.setenv("NEXUS_MODEL_STREAMING", "1")
                monkeypatch.setattr(model, "POLICY", old_policy + " Rotated policy.")
            return result

        monkeypatch.setattr(model, "read_bounded_body", rotate_after_read)
        response = c.post("/studio-api/respond", json=reviewed, headers=AUTH)
        assert response.status_code == 200, response.text
        assert response.json()["text"] == "Snapshot accepted"
        assert response.json()["model"] == original.model_id
        assert len(seen) == 1
        destination, provider_auth, payload = seen[0]
        assert destination == original.endpoint
        assert provider_auth == "Bearer provider-secret-not-for-browser"
        assert payload["model"] == original.model_id
        assert payload["messages"][0] == {"role": "system", "content": old_policy}
        assert payload["max_tokens" if initial_kind == "gemini" else "max_completion_tokens"] == 2048
        assert ("store" not in payload) if initial_kind == "gemini" else (payload["store"] is False)
        assert "rotated-upstream-secret" not in json.dumps(payload)
        assert c.get("/studio-api/status").json()["configuration_id"] != reviewed["configuration_id"]
        assert c.post("/studio-api/respond", json=reviewed, headers=AUTH).status_code == 401
        updated_auth = {"authorization": "Bearer new-studio-token-01234567890123456789"}
        assert c.post("/studio-api/respond", json=reviewed, headers=updated_auth).status_code == 409
        assert len(seen) == 1


def test_policy_change_invalidates_review_and_does_not_contact_provider(monkeypatch):
    calls = []
    def handler(req):
        calls.append(json.loads(req.content))
        return httpx.Response(200, json={"choices": [
            {"message": {"role": "assistant", "content": "Current policy answer"},
             "finish_reason": "stop"},
        ]})
    with configured(monkeypatch, handler) as c:
        old_id = c.get("/studio-api/status").json()["configuration_id"]
        assert old_id == BODY["configuration_id"]
        monkeypatch.setattr(model, "POLICY", model.POLICY + " Updated reviewed constraints.")
        new_id = c.get("/studio-api/status").json()["configuration_id"]
        assert new_id != old_id
        assert c.post("/studio-api/respond", json=BODY, headers=AUTH).status_code == 409
        assert not calls
        response = c.post("/studio-api/respond",
                          json={**BODY, "configuration_id": new_id}, headers=AUTH)
        assert response.status_code == 200
        assert calls[0]["messages"][0]["content"] == model.POLICY



def test_operator_readiness_requires_single_valid_studio_bearer_without_provider_contact(monkeypatch):
    monkeypatch.setenv("NEXUS_MODEL_MAX_REQUESTS_PER_PROCESS", "2")
    with configured(monkeypatch, lambda _: pytest.fail("diagnostics contacted provider")) as client:
        endpoint = "/studio-api/operator-readiness"
        assert client.get(endpoint).status_code == 401
        assert client.get(endpoint, headers={"authorization": "Bearer wrong"}).status_code == 401
        assert client.get(endpoint, headers={"authorization": "Basic " + TOKEN}).status_code == 401
        duplicate_headers = [("authorization", "Bearer " + TOKEN),
                             ("authorization", "Bearer " + TOKEN)]
        assert client.get(endpoint, headers=duplicate_headers).status_code == 401
        assert client.app.state.model_budget.snapshot()["attempted"] == 0


def test_operator_readiness_is_redacted_offline_and_uses_atomic_budget_snapshot(monkeypatch):
    monkeypatch.setenv("NEXUS_MODEL_MAX_REQUESTS_PER_PROCESS", "2")
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"choices": [
            {"message": {"role": "assistant", "content": "Accepted text"},
             "finish_reason": "stop"}]})
    with configured(monkeypatch, handler) as client:
        endpoint = "/studio-api/operator-readiness"
        ready = client.get(endpoint, headers=AUTH)
        assert ready.status_code == 200
        assert ready.headers["cache-control"] == "no-store"
        payload = ready.json()
        assert payload == {
            "readiness": "READY_TO_TEST",
            "configuration_valid": True,
            "model": "configured-test-model",
            "provider_host": "provider.example",
            "adapter": "generic",
            "streaming": False,
            "local_request_budget": {"limit": 2, "attempted": 0, "remaining": 2},
            "budget_scope": "one_process_until_restart",
            "provider_live_verification": "NOT_RECORDED",
            "provider_contact_attempted": False,
            "operator_next_step": "explicit_single_probe_smoke",
            "authority": "none",
        }
        for secret in [TOKEN, "provider-secret-not-for-browser",
                       "https://provider.example/v1/chat/completions"]:
            assert secret not in ready.text
        assert not calls
        assert client.post("/studio-api/respond", json=BODY, headers=AUTH).status_code == 200
        state = client.get(endpoint, headers=AUTH).json()
        assert state["local_request_budget"] == {"limit": 2, "attempted": 1, "remaining": 1}
        assert state["provider_live_verification"] == "NOT_RECORDED"
        assert client.post("/studio-api/respond", json=BODY, headers=AUTH).status_code == 200
        exhausted = client.get(endpoint, headers=AUTH).json()
        assert exhausted["readiness"] == "LOCAL_BUDGET_EXHAUSTED"
        assert exhausted["local_request_budget"] == {"limit": 2, "attempted": 2, "remaining": 0}
        assert exhausted["operator_next_step"] == "restart_or_set_provider_quota"
        assert client.post("/studio-api/respond", json=BODY, headers=AUTH).status_code == 429
        assert len(calls) == 2
        assert client.get(endpoint, headers=AUTH).json()["local_request_budget"] == exhausted["local_request_budget"]


def test_operator_readiness_is_available_without_provider_when_studio_token_is_valid(monkeypatch):
    monkeypatch.delenv("NEXUS_MODEL_URL", raising=False)
    monkeypatch.delenv("NEXUS_MODEL_ID", raising=False)
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", TOKEN)
    monkeypatch.setenv("NEXUS_MODEL_MAX_REQUESTS_PER_PROCESS", "1")
    with TestClient(main.app) as client:
        response = client.get("/studio-api/operator-readiness", headers=AUTH)
        assert response.status_code == 200
        payload = response.json()
        assert payload["readiness"] == "NOT_CONFIGURED"
        assert payload["configuration_valid"] is False
        assert payload["model"] is None and payload["provider_host"] is None
        assert payload["adapter"] is None and payload["streaming"] is False
        assert payload["operator_next_step"] == "configure_model_on_server"
        assert payload["local_request_budget"]["remaining"] == 1
        assert payload["provider_contact_attempted"] is False


def test_operator_readiness_unavailable_without_secure_studio_token(monkeypatch):
    monkeypatch.delenv("NEXUS_MODEL_URL", raising=False)
    monkeypatch.delenv("NEXUS_STUDIO_TOKEN", raising=False)
    with TestClient(main.app) as client:
        assert client.get("/studio-api/operator-readiness").status_code == 503
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", "short")
    with TestClient(main.app) as client:
        assert client.get("/studio-api/operator-readiness",
                          headers={"authorization": "Bearer short"}).status_code == 503


def test_operator_readiness_reports_gemini_without_verifying_remote_provider(monkeypatch):
    monkeypatch.setenv("NEXUS_MODEL_ADAPTER", "gemini")
    monkeypatch.setenv("NEXUS_MODEL_STREAMING", "1")
    with configured(monkeypatch, lambda _: pytest.fail("diagnostic reached Gemini")) as client:
        monkeypatch.setenv("NEXUS_MODEL_URL", model.GEMINI_CHAT_COMPLETIONS)
        response = client.get("/studio-api/operator-readiness", headers=AUTH)
        assert response.status_code == 200
        body = response.json()
        assert body["readiness"] == "READY_TO_TEST"
        assert body["provider_host"] == "generativelanguage.googleapis.com"
        assert body["adapter"] == "gemini" and body["streaming"] is True
        assert body["provider_live_verification"] == "NOT_RECORDED"
        assert body["provider_contact_attempted"] is False
        assert "provider-secret-not-for-browser" not in response.text


def test_operator_readiness_disabled_budget_never_claims_remote_availability(monkeypatch):
    monkeypatch.setenv("NEXUS_MODEL_MAX_REQUESTS_PER_PROCESS", "0")
    with configured(monkeypatch, lambda _: pytest.fail("disabled diagnostic contacted provider")) as client:
        r = client.get("/studio-api/operator-readiness", headers=AUTH)
        assert r.status_code == 200
        assert r.json()["readiness"] == "LOCAL_BUDGET_EXHAUSTED"
        assert r.json()["local_request_budget"] == {"limit": 0, "attempted": 0, "remaining": 0}
        assert r.json()["provider_live_verification"] == "NOT_RECORDED"
        assert client.post("/studio-api/respond", json=BODY, headers=AUTH).status_code == 429


def test_model_budget_defaults_to_small_local_attempt_limit_and_is_secret_safe(monkeypatch):
    monkeypatch.delenv("NEXUS_MODEL_MAX_REQUESTS_PER_PROCESS", raising=False)
    budget = model.ModelRequestBudget()
    assert budget.limit == 32
    assert "secret" not in repr(budget)
    for _ in range(32):
        assert budget.reserve() is True
    assert budget.reserve() is False


@pytest.mark.parametrize("value", ["", "-1", "not-a-number", "4097", "99999999999",
                                     " 2 ", "9" * 5000, "0x1", "1.0"])
def test_malformed_model_budget_fail_closed_before_provider(monkeypatch, value):
    monkeypatch.setenv("NEXUS_MODEL_MAX_REQUESTS_PER_PROCESS", value)
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"choices": [
            {"message": {"content": "should never reach provider"}, "finish_reason": "stop"}]})
    with configured(monkeypatch, handler) as client:
        assert client.app.state.model_budget.limit == 0
        response = client.post("/studio-api/respond", json=BODY, headers=AUTH)
        assert response.status_code == 429
        assert response.headers.get("cache-control") == "no-store"
    assert not calls


def test_request_budget_charges_only_authorized_reviewed_upstream_attempts(monkeypatch):
    monkeypatch.setenv("NEXUS_MODEL_MAX_REQUESTS_PER_PROCESS", "2")
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"choices": [
            {"message": {"role": "assistant", "content": "Capped model draft"},
             "finish_reason": "stop"}]})
    with configured(monkeypatch, handler) as client:
        budget = client.app.state.model_budget
        assert budget.limit == 2
        assert client.post("/studio-api/respond", json=BODY).status_code == 401
        assert client.post("/studio-api/respond",
                           json={**BODY, "consent": False}, headers=AUTH).status_code == 422
        assert client.post("/studio-api/respond",
                           json={**BODY, "configuration_id": "0" * 64}, headers=AUTH).status_code == 409
        assert budget._attempted == 0
        for _ in range(2):
            reply = client.post("/studio-api/respond", json=BODY, headers=AUTH)
            assert reply.status_code == 200
            assert reply.json()["text"] == "Capped model draft"
        assert budget._attempted == 2
        for _ in range(4):
            capped = client.post("/studio-api/respond", json=BODY, headers=AUTH)
            assert capped.status_code == 429
            assert capped.json()["detail"] == "Local model request budget exhausted or disabled"
        assert len(calls) == 2
        assert budget._attempted == 2


def test_request_budget_counts_stream_and_buffered_against_same_limit(monkeypatch):
    monkeypatch.setenv("NEXUS_MODEL_MAX_REQUESTS_PER_PROCESS", "1")
    monkeypatch.setenv("NEXUS_MODEL_STREAMING", "1")
    calls = []
    def handler(request):
        calls.append(request)
        payload = json.loads(request.content)
        assert payload["stream"] is True
        wire = sse({"role": "assistant"}) + sse({"content": "Streamed model draft"}) + sse({}, "stop") + DONE
        return httpx.Response(200, content=wire,
                              headers={"content-type": "text/event-stream"})
    with configured(monkeypatch, handler) as client:
        reviewed = {**BODY,
                    "configuration_id": client.get("/studio-api/status").json()["configuration_id"]}
        response = client.post("/studio-api/respond-stream", json=reviewed, headers=AUTH)
        assert response.status_code == 200
        assert any(frame["type"] == "done" for frame in map(json.loads, response.text.splitlines()))
        assert client.app.state.model_budget._attempted == 1
        capped = client.post("/studio-api/respond", json=reviewed, headers=AUTH)
        assert capped.status_code == 429
    assert len(calls) == 1


def test_model_request_budget_is_atomic_under_concurrency():
    from concurrent.futures import ThreadPoolExecutor
    budget = model.ModelRequestBudget("3")
    with ThreadPoolExecutor(max_workers=16) as pool:
        admitted = list(pool.map(lambda _: budget.reserve(), range(200)))
    assert admitted.count(True) == 3
    assert admitted.count(False) == 197
    assert budget._attempted == 3



def test_durable_budget_prevents_model_calls_after_gateway_restart(monkeypatch, tmp_path):
    root = tmp_path / "model-budget"
    root.mkdir(mode=0o700)
    monkeypatch.setenv("NEXUS_MODEL_BUDGET_DIR", str(root))
    monkeypatch.setenv("NEXUS_MODEL_MAX_REQUESTS_PER_PROCESS", "1")
    calls = []
    def handler(request):
        calls.append(1)
        return httpx.Response(200, json={"choices": [
            {"message": {"role": "assistant", "content": "A safe bounded model draft"},
             "finish_reason": "stop"}]})
    with configured(monkeypatch, handler) as client:
        status = client.get("/studio-api/operator-readiness", headers=AUTH).json()
        assert status["budget_scope"] == "one_private_host_directory_until_explicit_reset"
        assert status["readiness"] == "READY_TO_TEST"
        assert status["local_request_budget"] == {"limit": 1, "attempted": 0, "remaining": 1}
        assert client.post("/studio-api/respond", json=BODY, headers=AUTH).status_code == 200
    with configured(monkeypatch, handler) as client:
        status = client.get("/studio-api/operator-readiness", headers=AUTH).json()
        assert status["budget_scope"] == "one_private_host_directory_until_explicit_reset"
        assert status["readiness"] == "LOCAL_BUDGET_EXHAUSTED"
        assert status["local_request_budget"] == {"limit": 1, "attempted": 1, "remaining": 0}
        assert client.post("/studio-api/respond", json=BODY, headers=AUTH).status_code == 429
        assert client.app.state.model_budget.snapshot()["attempted"] == 1
    assert calls == [1]


def test_durable_budget_storage_unavailable_denies_provider_and_reports_honestly(monkeypatch, tmp_path):
    monkeypatch.setenv("NEXUS_MODEL_BUDGET_DIR", str(tmp_path / "missing-dir"))
    monkeypatch.setenv("NEXUS_MODEL_MAX_REQUESTS_PER_PROCESS", "3")
    with configured(monkeypatch, lambda _: pytest.fail("fail-closed quota reached provider")) as client:
        status = client.get("/studio-api/operator-readiness", headers=AUTH)
        assert status.status_code == 200
        payload = status.json()
        assert payload["readiness"] == "LOCAL_BUDGET_UNAVAILABLE"
        assert payload["budget_scope"] == "durable_store_unavailable"
        assert payload["local_request_budget"] == {"limit": 3, "attempted": None, "remaining": 0}
        assert payload["operator_next_step"] == "repair_private_budget_storage"
        assert client.post("/studio-api/respond", json=BODY, headers=AUTH).status_code == 429


def test_durable_budget_corruption_mid_gateway_denies_next_request(monkeypatch, tmp_path):
    root = tmp_path / "private-budget"
    root.mkdir(mode=0o700)
    monkeypatch.setenv("NEXUS_MODEL_BUDGET_DIR", str(root))
    monkeypatch.setenv("NEXUS_MODEL_MAX_REQUESTS_PER_PROCESS", "2")
    calls = []
    def handler(request):
        calls.append(1)
        return httpx.Response(200, json={"choices": [
            {"message": {"content": "Safe draft"}, "finish_reason": "stop"}]})
    with configured(monkeypatch, handler) as client:
        assert client.post("/studio-api/respond", json=BODY, headers=AUTH).status_code == 200
        counter = root / "model-attempts.counter"
        counter.write_text("invalid\n")
        assert client.post("/studio-api/respond", json=BODY, headers=AUTH).status_code == 429
        status = client.get("/studio-api/operator-readiness", headers=AUTH).json()
        assert status["readiness"] == "LOCAL_BUDGET_UNAVAILABLE"
        assert status["budget_scope"] == "one_private_host_directory_until_explicit_reset"
        assert status["local_request_budget"]["attempted"] is None
        assert calls == [1]


def test_gateway_restart_recreates_local_budget_not_global_provider_spend(monkeypatch):
    monkeypatch.setenv("NEXUS_MODEL_MAX_REQUESTS_PER_PROCESS", "1")
    with configured(monkeypatch) as first:
        assert first.post("/studio-api/respond", json=BODY, headers=AUTH).status_code == 200
        assert first.post("/studio-api/respond", json=BODY, headers=AUTH).status_code == 429
    # A separate worker/restart gets its own cap. This must not be presented
    # as a provider-side cost limit or a durable service-wide quota.
    with configured(monkeypatch) as second:
        assert second.app.state.model_budget.limit == 1
        assert second.post("/studio-api/respond", json=BODY, headers=AUTH).status_code == 200


def test_real_loopback_http_provider_transport(monkeypatch):
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    seen=[]
    class Provider(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            seen.append((self.path,self.headers.get('authorization'),json.loads(self.rfile.read(int(self.headers['content-length'])))))
            raw=json.dumps({'choices':[{'message':{'content':'Synthetic loopback provider response'},'finish_reason':'stop'}]}).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    server=ThreadingHTTPServer(('127.0.0.1',0),Provider)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        monkeypatch.setenv('NEXUS_MODEL_URL',f'http://127.0.0.1:{server.server_port}/v1/chat/completions')
        monkeypatch.setenv('NEXUS_MODEL_ID','synthetic-loopback')
        monkeypatch.setenv('NEXUS_STUDIO_TOKEN',TOKEN)
        monkeypatch.setenv('NEXUS_MODEL_API_KEY','loopback-provider-key')
        body={**BODY,'configuration_id':model.configuration_id(model.config())}
        with TestClient(main.app) as c:
            response=c.post('/studio-api/respond',json=body,headers=AUTH)
            assert response.status_code==200,response.text
            assert response.json()['text']=='Synthetic loopback provider response'
        assert len(seen)==1
        assert seen[0][0]=='/v1/chat/completions' and seen[0][1]=='Bearer loopback-provider-key'
        assert seen[0][2]['messages'][0]['content']==model.POLICY
    finally:server.shutdown();server.server_close();thread.join(timeout=2)


def test_short_gateway_credentials_leave_model_disabled(monkeypatch):
    with configured(monkeypatch):
        monkeypatch.setenv('NEXUS_STUDIO_TOKEN','short')
        assert model.config() is None


@pytest.mark.parametrize('mode,expected',[('thinking','enabled'),('non-thinking','disabled')])
def test_deepseek_modes_bind_review_and_forward_real_flag(monkeypatch,mode,expected):
    import json
    monkeypatch.setenv('NEXUS_MODEL_ADAPTER','deepseek')
    def handler(req):
        payload=json.loads(req.content)
        assert payload['thinking']=={'type':expected}
        assert payload['max_tokens']==4096 and 'max_completion_tokens' not in payload
        return httpx.Response(200,json={'choices':[{'message':{'content':'Result','reasoning_content':'private reasoning not returned'},'finish_reason':'stop'}]})
    with configured(monkeypatch,handler) as c:
        status=c.get('/studio-api/status').json()
        assert mode in status['modes']
        assert status['configuration_id']!=BODY['configuration_id']
        assert c.post('/studio-api/respond',json=BODY,headers=AUTH).status_code==409
        r=c.post('/studio-api/respond',json={**BODY,'configuration_id':status['configuration_id'],'mode':mode,'max_output_tokens':4096},headers=AUTH)
        assert r.status_code==200 and r.json()['mode']==mode
        assert 'private reasoning' not in r.text



def test_gemini_config_is_disabled_without_exact_host_path_and_provider_key(monkeypatch):
    monkeypatch.setenv("NEXUS_MODEL_ADAPTER", "gemini")
    with configured(monkeypatch):
        monkeypatch.setenv("NEXUS_MODEL_URL", model.GEMINI_CHAT_COMPLETIONS)
        assert model.config() is not None
        monkeypatch.setenv("NEXUS_MODEL_API_KEY", "")
        assert model.config() is None
        monkeypatch.setenv("NEXUS_MODEL_API_KEY", "gemini-test-secret")
        for url in [
            "https://provider.example/v1beta/openai/chat/completions",
            "http://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            "https://generativelanguage.googleapis.com:444/v1beta/openai/chat/completions",
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions/",
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions?key=secret",
            "https://generativelanguage.googleapis.com/v1beta/openai/other",
            "https://generativelanguage.googleapis.com.evil.invalid/v1beta/openai/chat/completions",
        ]:
            monkeypatch.setenv("NEXUS_MODEL_URL", url)
            assert model.config() is None, url
        monkeypatch.setenv("NEXUS_MODEL_URL", model.GEMINI_CHAT_COMPLETIONS)
        assert model.config() is not None


def test_gemini_buffered_completion_requires_consent_and_uses_compatible_wire(monkeypatch):
    monkeypatch.setenv("NEXUS_MODEL_ADAPTER", "gemini")
    requests = []
    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        assert str(request.url) == model.GEMINI_CHAT_COMPLETIONS
        assert request.headers["authorization"] == "Bearer provider-secret-not-for-browser"
        assert payload["model"] == "configured-test-model"
        assert payload["messages"][0] == {"role": "system", "content": model.POLICY}
        assert payload["messages"][1:] == BODY["messages"]
        assert payload["max_tokens"] == 2048
        assert payload["stream"] is False
        assert not any(key in payload for key in ("max_completion_tokens", "store",
                                                 "tools", "thinking", "reasoning_effort"))
        return httpx.Response(200, json={
            "choices": [{"message": {"role": "assistant", "content": "Gemini-compatible draft"},
                         "finish_reason": "stop"}],
        })
    with configured(monkeypatch, handler) as c:
        monkeypatch.setenv("NEXUS_MODEL_URL", model.GEMINI_CHAT_COMPLETIONS)
        status = c.get("/studio-api/status").json()
        assert status["configured"] is True
        assert status["provider_host"] == "generativelanguage.googleapis.com"
        assert status["authority"] == "none"
        assert "modes" not in status
        assert status["configuration_id"] != BODY["configuration_id"]
        assert "provider-secret-not-for-browser" not in json.dumps(status)
        assert c.post("/studio-api/respond", json=BODY, headers=AUTH).status_code == 409
        reviewed = {**BODY, "configuration_id": status["configuration_id"]}
        assert c.post("/studio-api/respond", json=reviewed, headers=AUTH).json()["text"] == "Gemini-compatible draft"
        assert c.post("/studio-api/respond", json={**reviewed, "mode": "thinking"}, headers=AUTH).status_code == 422
        assert c.post("/studio-api/respond", json={**reviewed, "mode": "non-thinking"}, headers=AUTH).status_code == 422
        assert c.post("/studio-api/respond", json={**reviewed, "consent": False}, headers=AUTH).status_code == 422
        assert c.post("/studio-api/respond", json=reviewed, headers={}).status_code == 401
        monkeypatch.setenv("NEXUS_MODEL_ADAPTER", "generic")
        assert c.post("/studio-api/respond", json=reviewed, headers=AUTH).status_code == 409
    assert len(requests) == 1


def test_gemini_streaming_preserves_text_only_approval_and_no_tools(monkeypatch):
    monkeypatch.setenv("NEXUS_MODEL_ADAPTER", "gemini")
    monkeypatch.setenv("NEXUS_MODEL_STREAMING", "1")
    wire = sse({"role": "assistant", "reasoning_content": "private thoughts"}) + \
        sse({"content": "Reviewed streaming reply"}) + sse({}, "stop") + DONE
    def handler(request):
        payload = json.loads(request.content)
        assert str(request.url) == model.GEMINI_CHAT_COMPLETIONS
        assert payload["stream"] is True and payload["max_tokens"] == 2048
        assert "store" not in payload and "tools" not in payload
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=wire)
    with configured(monkeypatch, handler) as client:
        monkeypatch.setenv("NEXUS_MODEL_URL", model.GEMINI_CHAT_COMPLETIONS)
        status = client.get("/studio-api/status").json()
        assert status["streaming"] is True
        reviewed = {**BODY, "configuration_id": status["configuration_id"]}
        response = client.post("/studio-api/respond-stream", json=reviewed, headers=AUTH)
        assert response.status_code == 200
        frames = [json.loads(line) for line in response.text.splitlines()]
        assert [f["type"] for f in frames] == ["delta", "done"]
        assert frames[0]["text"] == "Reviewed streaming reply"
        assert frames[-1]["authority"] == "none" and frames[-1]["origin"] == "model"
        assert "private thoughts" not in response.text


@pytest.mark.parametrize('fields',[{'mode':'thinking'},{'mode':'non-thinking'},{'max_output_tokens':True},{'max_output_tokens':8193},{'max_output_tokens':0},{'max_output_tokens':1.2},{'mode':'made-up'}])
def test_modes_and_budgets_fail_before_upstream(monkeypatch,fields):
    with configured(monkeypatch,lambda _:pytest.fail('unsupported input reached provider')) as c:
        assert c.post('/studio-api/respond',json={**BODY,**fields},headers=AUTH).status_code==422


@pytest.mark.parametrize('raw',[
    b'[' * 40000 + b'0' + b']' * 40000,
    b'{"choices":[{"message":{"content":"\\ud800"},"finish_reason":"stop"}]}',
],ids=['deeply-nested-json','invalid-unicode-text'])
def test_malformed_provider_output_is_contained_and_capacity_recovers(monkeypatch,raw):
    replies=iter([httpx.Response(200,content=raw),httpx.Response(200,json={
        'choices':[{'message':{'content':'Recovered draft'},'finish_reason':'stop'}]})])
    with configured(monkeypatch,lambda _:next(replies)) as c:
        r=c.post('/studio-api/respond',json=BODY,headers=AUTH)
        assert r.status_code==502
        assert r.json()['detail']=='Invalid text-only model response'
        assert c.post('/studio-api/respond',json=BODY,headers=AUTH).json()['text']=='Recovered draft'


def sse(delta, finish=None):
    return ("data: " + json.dumps({
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }, ensure_ascii=False) + "\r\n\r\n").encode()


DONE = b"data: [DONE]\r\n\r\n"


@pytest.mark.parametrize("finish", ["stop", "length"])
def test_streamed_transport_binds_review_and_only_emits_answer_text(monkeypatch, finish):
    monkeypatch.setenv("NEXUS_MODEL_STREAMING", "1")
    visible = "برای 🌙"
    wire = (b": keepalive\r\n\r\n" + sse({"role": "assistant", "reasoning_content": "private"})
            + sse({"content": visible}) + sse({}, finish) + DONE)

    class Bytes(httpx.AsyncByteStream):
        async def __aiter__(self):
            for offset in range(0, len(wire), 3):
                yield wire[offset:offset + 3]

    def handler(request):
        payload = json.loads(request.content)
        assert payload["stream"] is True and payload["store"] is False
        assert payload["messages"][0]["content"] == model.POLICY
        assert payload["messages"][1:] == BODY["messages"]
        assert request.headers["accept"] == "text/event-stream"
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=Bytes())

    with configured(monkeypatch, handler) as client:
        status = client.get("/studio-api/status").json()
        assert status["streaming"] is True
        route = "/studio-api/respond-stream"
        assert client.post(route, json=BODY, headers=AUTH).status_code == 409
        body = {**BODY, "configuration_id": status["configuration_id"]}
        assert client.post(route, json=body).status_code == 401
        assert client.post(route, json={**body, "consent": False}, headers=AUTH).status_code == 422
        response = client.post(route, json=body, headers=AUTH)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/x-ndjson"
        assert response.headers["cache-control"] == "no-store"
        assert list(map(json.loads, response.text.splitlines())) == [
            {"type": "delta", "text": visible},
            {"type": "done", "origin": "model", "model": "configured-test-model",
             "truncated": finish == "length", "authority": "none",
             "model_slot": "primary", "configuration_id": status["configuration_id"]},
        ]


def test_stream_is_opt_in_and_preserves_buffered_requests(monkeypatch):
    monkeypatch.delenv("NEXUS_MODEL_STREAMING", raising=False)
    with configured(monkeypatch) as client:
        assert "streaming" not in client.get("/studio-api/status").json()
        assert client.post("/studio-api/respond-stream", json=BODY, headers=AUTH).status_code == 503
        assert client.post("/studio-api/respond", json=BODY, headers=AUTH).json()["text"] == "Model draft"


@pytest.mark.parametrize("tail", [
    b"", DONE, sse({}, "stop"), sse({"tool_calls": [{}]}) + DONE,
    sse({"content": "🌙" * 12000}) + DONE, sse({"content": "x" * 128001}) + DONE,
])
def test_stream_without_valid_bounded_completion_has_no_done_frame(monkeypatch, tail):
    monkeypatch.setenv("NEXUS_MODEL_STREAMING", "1")
    with configured(monkeypatch, lambda _: httpx.Response(
        200, headers={"content-type": "text/event-stream"}, content=sse({"content": "Draft"}) + tail,
    )) as client:
        body = {**BODY, "configuration_id": model.configuration_id(model.config())}
        for _ in range(5):
            response = client.post("/studio-api/respond-stream", json=body, headers=AUTH)
            frames = list(map(json.loads, response.text.splitlines()))
            assert frames[-1] == {"type": "error", "reason": "incomplete"}
            assert not any(frame["type"] == "done" for frame in frames)


def test_stream_disconnect_closes_silent_upstream_and_releases_capacity(monkeypatch):
    from types import SimpleNamespace

    async def exercise():
        first_delta = anyio.Event()
        upstream_closed = anyio.Event()
        limiter = anyio.CapacityLimiter(1)

        class Paused(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield sse({"content": "Before disconnect"})
                await anyio.sleep_forever()

            async def aclose(self):
                upstream_closed.set()

        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(
            200, headers={"content-type": "text/event-stream"}, stream=Paused(),
        ))) as client:
            request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(client=client, model_limiter=limiter)))
            response = model.CompletionStream(model.response_frames(
                request, "https://provider.example", {}, {"model": "test", "stream": True},
            ))

            async def receive():
                await first_delta.wait()
                return {"type": "http.disconnect"}

            async def send(message):
                if b"Before disconnect" in message.get("body", b""):
                    assert limiter.borrowed_tokens == 1
                    first_delta.set()

            with anyio.fail_after(2):
                await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send)
            assert upstream_closed.is_set() and limiter.borrowed_tokens == 0

    anyio.run(exercise)
