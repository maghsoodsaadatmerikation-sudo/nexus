"""Synthetic-only contract for a strictly free OpenRouter model route."""
import json
import os

from fastapi.testclient import TestClient
import httpx
import pytest

import main
import studio_model as model
import model_quality_eval as quality

TOKEN = "synthetic-free-studio-token-0123456789"
MODEL = "fixture/small-chat:free"


@pytest.fixture
def settings(monkeypatch):
    for name in os.environ:
        if name.startswith("NEXUS_MODEL_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", TOKEN)
    monkeypatch.setenv("NEXUS_MODEL_URL", model.OPENROUTER_CHAT_COMPLETIONS)
    monkeypatch.setenv("NEXUS_MODEL_ID", MODEL)
    monkeypatch.setenv("NEXUS_MODEL_ADAPTER", "openrouter-free")
    monkeypatch.setenv("NEXUS_MODEL_API_KEY", "synthetic-free-provider-key")
    return monkeypatch


@pytest.mark.parametrize("name,value", [
    ("NEXUS_MODEL_URL", "https://unrelated.example/api/v1/chat/completions"),
    ("NEXUS_MODEL_URL", model.OPENROUTER_CHAT_COMPLETIONS + "?route=paid"),
    ("NEXUS_MODEL_API_KEY", ""),
    ("NEXUS_MODEL_ID", "fixture/small-chat"),
    ("NEXUS_MODEL_ID", "fixture/small-chat:free:nitro"),
    ("NEXUS_MODEL_ID", "openrouter/auto"),
    ("NEXUS_MODEL_ID", "openrouter/free"),
    ("NEXUS_MODEL_ID", "fixture/small-chat:free\npaid"),
])
def test_nonfree_or_ambiguous_configuration_is_disabled(settings, name, value):
    settings.setenv(name, value)
    assert model.read_model_settings() is None


@pytest.mark.parametrize("stream", [False, True])
def test_payload_demands_zero_price_and_disables_fallbacks(settings, stream):
    payload = model.provider_payload(MODEL, [{"role": "user", "content": "Synthetic"}],
                                     stream=stream, max_output_tokens=64)
    assert payload == {
        "model": MODEL, "messages": [{"role": "user", "content": "Synthetic"}],
        "stream": stream, "max_tokens": 64,
        "provider": {"max_price": {"prompt": 0, "completion": 0, "request": 0},
                     "allow_fallbacks": False},
    }
    with pytest.raises(ValueError):
        model.provider_payload("fixture/paid", [], stream=stream, max_output_tokens=64)
    with pytest.raises(ValueError):
        model.provider_payload(MODEL, [], stream=stream, max_output_tokens=64, mode="thinking")


@pytest.mark.parametrize("status", [200, 402, 429, 503])
def test_gateway_sends_one_free_only_request_without_paid_retry(settings, status):
    calls = []

    def provider(request):
        calls.append(request)
        assert str(request.url) == model.OPENROUTER_CHAT_COMPLETIONS
        assert request.headers["authorization"] == "Bearer synthetic-free-provider-key"
        assert TOKEN not in request.content.decode() + str(request.headers)
        payload = json.loads(request.content)
        assert payload["model"] == MODEL and "models" not in payload
        assert payload["provider"]["allow_fallbacks"] is False
        assert set(payload["provider"]["max_price"].values()) == {0}
        return httpx.Response(status, json={"choices": [{"message": {"content": "Synthetic free reply"},
                                                        "finish_reason": "stop"}]})

    with TestClient(main.app) as client:
        with httpx.Client(transport=httpx.MockTransport(provider)) as sync_client:
            # The evaluator must use the same restrictions as production.
            if status == 200:
                assert quality.query_provider(sync_client, model.read_model_settings(), quality.PROBES[0]) == "Synthetic free reply"
                calls.clear()
        async_client = httpx.AsyncClient(transport=httpx.MockTransport(provider))
        original = main.app.state.client
        main.app.state.client = async_client
        try:
            configuration = client.get("/studio-api/status").json()
            assert configuration["configured"] is True
            body = {"consent": True, "configuration_id": configuration["configuration_id"],
                    "messages": [{"role": "user", "content": "Synthetic reviewed request"}]}
            assert client.post("/studio-api/respond", json=body).status_code == 401
            assert calls == []
            response = client.post("/studio-api/respond", json=body,
                                   headers={"authorization": "Bearer " + TOKEN})
            assert response.status_code == (200 if status == 200 else 503 if status in {429, 503} else 502)
            assert len(calls) == 1
            assert main.app.state.model_budget.snapshot()["attempted"] == 1
            assert "synthetic-free-provider-key" not in response.text
        finally:
            client.portal.call(async_client.aclose)
            main.app.state.client = original
