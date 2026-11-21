"""Offline, secret-safe, consent-bound multi-model routing contract."""
from contextlib import contextmanager
import json

import httpx
import pytest
from fastapi.testclient import TestClient

import main
import studio_model as model

TOKEN = "studio-access-token-01234567890123456789"
AUTH = {"authorization": "Bearer " + TOKEN}
SECRET_PRIMARY = "private-primary-provider-key"
SECRET_CLAUDE = "private-claude-provider-key"
SECRET_GEMINI = "private-gemini-provider-key"


def chat_answer(message):
    return {"choices": [{"message": {"role": "assistant", "content": message},
                         "finish_reason": "stop"}]}


def claude_answer(message):
    return {"type": "message", "role": "assistant",
            "content": [{"type": "text", "text": message}],
            "stop_reason": "end_turn"}


@contextmanager
def configured(monkeypatch, handler):
    for slot in ("SECONDARY", "TERTIARY"):
        for field in model._SLOT_FIELDS:
            monkeypatch.delenv("NEXUS_MODEL_" + slot + "_" + field, raising=False)
    monkeypatch.setenv("NEXUS_MODEL_URL", "https://primary.example/v1/chat/completions")
    monkeypatch.setenv("NEXUS_MODEL_ID", "primary-text")
    monkeypatch.setenv("NEXUS_MODEL_API_KEY", SECRET_PRIMARY)
    monkeypatch.setenv("NEXUS_MODEL_ADAPTER", "generic")
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", TOKEN)
    monkeypatch.delenv("NEXUS_MODEL_WORKSPACE_ID", raising=False)
    monkeypatch.delenv("NEXUS_MODEL_STREAMING", raising=False)
    monkeypatch.delenv("NEXUS_MODEL_BUDGET_DIR", raising=False)
    monkeypatch.setenv("NEXUS_MODEL_MAX_REQUESTS_PER_PROCESS", "8")
    with TestClient(main.app) as client:
        original = client.app.state.client
        upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False)
        client.app.state.client = upstream
        try:
            yield client
        finally:
            client.portal.call(upstream.aclose)
            client.app.state.client = original


def set_secondary(monkeypatch):
    monkeypatch.setenv("NEXUS_MODEL_SECONDARY_URL", model.ANTHROPIC_MESSAGES)
    monkeypatch.setenv("NEXUS_MODEL_SECONDARY_ID", "claude-secondary")
    monkeypatch.setenv("NEXUS_MODEL_SECONDARY_ADAPTER", "anthropic")
    monkeypatch.setenv("NEXUS_MODEL_SECONDARY_API_KEY", SECRET_CLAUDE)


def set_tertiary(monkeypatch):
    monkeypatch.setenv("NEXUS_MODEL_TERTIARY_URL", model.GEMINI_CHAT_COMPLETIONS)
    monkeypatch.setenv("NEXUS_MODEL_TERTIARY_ID", "gemini-tertiary")
    monkeypatch.setenv("NEXUS_MODEL_TERTIARY_ADAPTER", "gemini")
    monkeypatch.setenv("NEXUS_MODEL_TERTIARY_API_KEY", SECRET_GEMINI)


def review(status, slot="primary"):
    choice = next((c for c in status.get("models", []) if c["slot"] == slot), None)
    return {"consent": True, "model_slot": slot,
            "configuration_id": choice["configuration_id"] if choice else status["configuration_id"],
            "messages": [{"role": "user", "content": "Fictional prompt for a reviewed model."}]}


def test_primary_only_preserves_legacy_wire_and_public_status(monkeypatch):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=chat_answer("Primary answer"))
    with configured(monkeypatch, handler) as client:
        state = client.get("/studio-api/status").json()
        assert "models" not in state
        assert state["model"] == "primary-text"
        assert set(model.read_model_catalog()) == {"primary"}
        payload = review(state)
        payload.pop("model_slot")
        response = client.post("/studio-api/respond", json=payload, headers=AUTH)
        assert response.status_code == 200 and response.json()["model"] == "primary-text"
        assert len(seen) == 1 and seen[0].headers["authorization"] == "Bearer " + SECRET_PRIMARY


def test_multi_catalog_exposes_only_reviewable_choices_without_provider_probes(monkeypatch):
    with configured(monkeypatch, lambda _: pytest.fail("status contacted a provider")) as client:
        set_secondary(monkeypatch)
        set_tertiary(monkeypatch)
        state = client.get("/studio-api/status")
        assert state.status_code == 200 and state.headers["cache-control"] == "no-store"
        data = state.json()
        assert data["configured"] is True and data["model"] == "primary-text"
        assert [c["slot"] for c in data["models"]] == ["primary", "secondary", "tertiary"]
        assert [c["model"] for c in data["models"]] == ["primary-text", "claude-secondary", "gemini-tertiary"]
        assert len({c["configuration_id"] for c in data["models"]}) == 3
        assert {c["provider_host"] for c in data["models"]} == {
            "primary.example", "api.anthropic.com", "generativelanguage.googleapis.com"}
        for forbidden in (SECRET_PRIMARY, SECRET_CLAUDE, SECRET_GEMINI, TOKEN,
                          model.ANTHROPIC_MESSAGES, model.GEMINI_CHAT_COMPLETIONS):
            assert forbidden not in state.text
        assert client.app.state.model_budget.snapshot()["attempted"] == 0


def test_selected_credentials_and_provider_protocols_never_mix(monkeypatch):
    observed = []
    def handler(request):
        body = json.loads(request.content)
        observed.append((request, body))
        if str(request.url) == model.ANTHROPIC_MESSAGES:
            assert request.headers["x-api-key"] == SECRET_CLAUDE
            assert "authorization" not in request.headers
            assert body["model"] == "claude-secondary"
            assert body["system"] == model.POLICY
            assert body["stream"] is False and body["max_tokens"] == 2048
            return httpx.Response(200, json=claude_answer("Claude reply"))
        if str(request.url) == model.GEMINI_CHAT_COMPLETIONS:
            assert request.headers["authorization"] == "Bearer " + SECRET_GEMINI
            assert "x-api-key" not in request.headers
            assert body["model"] == "gemini-tertiary"
            assert "store" not in body
            return httpx.Response(200, json=chat_answer("Gemini reply"))
        assert str(request.url) == "https://primary.example/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer " + SECRET_PRIMARY
        assert body["model"] == "primary-text"
        return httpx.Response(200, json=chat_answer("Primary reply"))
    with configured(monkeypatch, handler) as client:
        set_secondary(monkeypatch)
        set_tertiary(monkeypatch)
        state = client.get("/studio-api/status").json()
        for slot, expected in [("secondary", "Claude reply"), ("tertiary", "Gemini reply"),
                               ("primary", "Primary reply")]:
            resp = client.post("/studio-api/respond", json=review(state, slot), headers=AUTH)
            assert resp.status_code == 200, resp.text
            assert resp.json()["text"] == expected
        assert len(observed) == 3
        assert client.app.state.model_budget.snapshot()["attempted"] == 3


def test_cross_slot_review_replay_unknown_slot_and_no_consents_fail_closed(monkeypatch):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=chat_answer("Never called"))
    with configured(monkeypatch, handler) as client:
        set_secondary(monkeypatch)
        state = client.get("/studio-api/status").json()
        approved = review(state, "primary")
        assert client.post("/studio-api/respond", json={**approved, "model_slot": "secondary"},
                           headers=AUTH).status_code == 409
        assert client.post("/studio-api/respond", json={**approved, "model_slot": "unlisted"},
                           headers=AUTH).status_code == 422
        assert client.post("/studio-api/respond", json=review(state, "secondary")).status_code == 401
        assert client.post("/studio-api/respond",
                           json={**review(state, "secondary"), "consent": False},
                           headers=AUTH).status_code == 422
        assert client.post("/studio-api/respond",
                           json={**review(state, "secondary"), "url": "https://attacker.invalid"},
                           headers=AUTH).status_code == 422
        assert calls == []
        assert client.app.state.model_budget.snapshot()["attempted"] == 0


@pytest.mark.parametrize("mutation", [
    {"URL": "http://attacker.example/v1/messages"},
    {"URL": "https://api.anthropic.com/v1/messages?steal=1"},
    {"WORKSPACE_ID": "wrkspc_x\r\nInjected: yes"},
    {"STREAMING": "1"},
    {"API_KEY": ""},
])
def test_invalid_optional_model_is_never_advertised_or_contacted(monkeypatch, mutation):
    with configured(monkeypatch, lambda _: pytest.fail("invalid slot forwarded")) as client:
        set_secondary(monkeypatch)
        for name, value in mutation.items():
            monkeypatch.setenv("NEXUS_MODEL_SECONDARY_" + name, value)
        state = client.get("/studio-api/status").json()
        assert "models" not in state
        stale = {"consent": True, "model_slot": "secondary",
                 "configuration_id": "a" * 64, "messages": [{"role": "user", "content": "Hi"}]}
        assert client.post("/studio-api/respond", json=stale, headers=AUTH).status_code == 409
        assert client.app.state.model_budget.snapshot()["attempted"] == 0


def test_removed_model_requires_new_review_and_does_not_fallback_to_primary(monkeypatch):
    requests = []
    with configured(monkeypatch, lambda req: (requests.append(req),
         httpx.Response(200, json=chat_answer("Unsafe fallback")))[1]) as client:
        set_secondary(monkeypatch)
        old = review(client.get("/studio-api/status").json(), "secondary")
        monkeypatch.delenv("NEXUS_MODEL_SECONDARY_API_KEY")
        assert client.post("/studio-api/respond", json=old, headers=AUTH).status_code == 409
        assert requests == []
        assert client.app.state.model_budget.snapshot()["attempted"] == 0


def test_selected_model_configuration_snapshot_survives_environment_rotation(monkeypatch):
    observed = []
    def handler(request):
        observed.append((str(request.url), request.headers.get("x-api-key")))
        return httpx.Response(200, json=claude_answer("Frozen selection"))
    with configured(monkeypatch, handler) as client:
        set_secondary(monkeypatch)
        old = review(client.get("/studio-api/status").json(), "secondary")
        real = model.read_bounded_body
        async def rotate(*args, **kwargs):
            result = await real(*args, **kwargs)
            monkeypatch.setenv("NEXUS_MODEL_SECONDARY_API_KEY", "rotated-private-key")
            monkeypatch.setenv("NEXUS_MODEL_SECONDARY_URL", "https://attacker.example/v1/messages")
            return result
        monkeypatch.setattr(model, "read_bounded_body", rotate)
        response = client.post("/studio-api/respond", json=old, headers=AUTH)
        assert response.status_code == 200
        assert observed == [(model.ANTHROPIC_MESSAGES, SECRET_CLAUDE)]
        assert client.post("/studio-api/respond", json=old, headers=AUTH).status_code == 409


def test_shared_global_attempt_budget_applies_across_all_selections(monkeypatch):
    seen = []
    with configured(monkeypatch, lambda req: (seen.append(req),
         httpx.Response(200, json=chat_answer("Limited answer")))[1]) as client:
        set_tertiary(monkeypatch)
        client.app.state.model_budget.limit = 1
        state = client.get("/studio-api/status").json()
        first = client.post("/studio-api/respond", json=review(state, "tertiary"), headers=AUTH)
        assert first.status_code == 200
        second = client.post("/studio-api/respond", json=review(state, "primary"), headers=AUTH)
        assert second.status_code == 429
        assert len(seen) == 1


def test_alternate_streaming_and_execution_modes_are_slot_specific(monkeypatch):
    with configured(monkeypatch, lambda _: pytest.fail("rejected mode reached provider")) as client:
        set_secondary(monkeypatch)
        state = client.get("/studio-api/status").json()
        secondary = review(state, "secondary")
        assert client.post("/studio-api/respond-stream", json=secondary, headers=AUTH).status_code == 503
        assert client.post("/studio-api/respond", json={**secondary, "mode": "thinking"},
                           headers=AUTH).status_code == 422
        assert client.app.state.model_budget.snapshot()["attempted"] == 0



def test_secondary_credential_rotation_revokes_the_previous_review(monkeypatch):
    calls = []
    with configured(monkeypatch, lambda req: (calls.append(req),
         httpx.Response(200, json=claude_answer("Old account answer")))[1]) as client:
        set_secondary(monkeypatch)
        previous = client.get("/studio-api/status").json()
        payload = review(previous, "secondary")
        monkeypatch.setenv("NEXUS_MODEL_SECONDARY_API_KEY", "fresh-private-claude-key")
        current = client.get("/studio-api/status").json()
        refreshed = review(current, "secondary")
        assert refreshed["configuration_id"] != payload["configuration_id"]
        assert client.post("/studio-api/respond", json=payload, headers=AUTH).status_code == 409
        assert calls == []
        response = client.post("/studio-api/respond", json=refreshed, headers=AUTH)
        assert response.status_code == 200
        assert calls[0].headers["x-api-key"] == "fresh-private-claude-key"


def test_secondary_operator_quality_preflight_and_mock_smoke(monkeypatch):
    import model_quality_eval as quality
    with configured(monkeypatch, lambda _: pytest.fail("preflight must be offline")):
        set_secondary(monkeypatch)
        assert quality.configuration_preflight("secondary")["status"] == "READY_TO_TEST"
        assert quality.configuration_preflight("tertiary")["status"] == "NOT_READY"
        snapshot = model.read_model_catalog()["secondary"]
        calls = []
        def handler(request):
            calls.append(request)
            assert str(request.url) == model.ANTHROPIC_MESSAGES
            assert request.headers["x-api-key"] == SECRET_CLAUDE
            return httpx.Response(200, json=claude_answer(quality.PROBES[0].good_reply))
        with httpx.Client(transport=httpx.MockTransport(handler), trust_env=False) as http:
            output = quality.smoke_live(http, snapshot)
        assert output["status"] == "PASS"
        assert output["quality_gate"] == "NOT_RUN"
        assert len(calls) == 1
        for secret in (SECRET_CLAUDE, TOKEN):
            assert secret not in json.dumps(output)


def test_model_catalog_excludes_optional_routes_if_primary_auth_is_missing(monkeypatch):
    with configured(monkeypatch, lambda _: pytest.fail("disabled catalog reached provider")) as client:
        set_secondary(monkeypatch)
        monkeypatch.setenv("NEXUS_STUDIO_TOKEN", "short")
        assert model.read_model_catalog() == {}
        state = client.get("/studio-api/status").json()
        assert state["configured"] is False
        assert "models" not in state
        assert client.post("/studio-api/respond",
                           json={"consent": True, "model_slot": "secondary",
                                 "configuration_id": "a" * 64,
                                 "messages": [{"role": "user", "content": "Test"}]},
                           headers=AUTH).status_code == 503
