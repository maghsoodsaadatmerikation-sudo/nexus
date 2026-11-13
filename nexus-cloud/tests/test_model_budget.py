"""Model dispatch budgets; synthetic requests never contact paid model providers."""
from contextlib import contextmanager

import httpx
import pytest
from fastapi.testclient import TestClient

import main
import studio_model as model

TOKEN = "synthetic-model-access-01234567890123456789"
AUTH = {"authorization": "Bearer " + TOKEN}


@contextmanager
def configured(monkeypatch, handler):
    monkeypatch.setenv("NEXUS_MODEL_URL", "https://provider.example/v1/chat/completions")
    monkeypatch.setenv("NEXUS_MODEL_ID", "budget-fixture")
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", TOKEN)
    monkeypatch.setenv("NEXUS_MODEL_ADAPTER", "generic")
    with TestClient(main.app) as client:
        original = client.app.state.client
        upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client.app.state.client = upstream
        try:
            yield client
        finally:
            client.portal.call(upstream.aclose)
            client.app.state.client = original


def body():
    c = model.config()
    return {
        "consent": True,
        "configuration_id": model.configuration_id(c),
        "messages": [{"role": "user", "content": "Explicitly reviewed synthetic request"}],
    }


def provider_response(_request):
    return httpx.Response(200, json={"choices": [
        {"message": {"content": "Synthetic reply"}, "finish_reason": "stop"}
    ]})


def test_call_budget_blocks_extra_dispatch_and_reports_retry(monkeypatch):
    monkeypatch.setenv("NEXUS_MODEL_MAX_CALLS_PER_HOUR", "1")
    count = 0
    def provider(request):
        nonlocal count
        count += 1
        return provider_response(request)
    with configured(monkeypatch, provider) as client:
        assert client.post("/studio-api/respond", json=body(), headers=AUTH).status_code == 200
        retry = client.post("/studio-api/respond", json=body(), headers=AUTH)
        assert retry.status_code == 429
        assert int(retry.headers["retry-after"]) >= 1
        assert retry.headers["cache-control"] == "no-store"
        assert client.app.state.model_budget.calls == 1
    assert count == 1


def test_output_token_reservation_rejects_before_provider_call(monkeypatch):
    monkeypatch.setenv("NEXUS_MODEL_MAX_CALLS_PER_HOUR", "5")
    monkeypatch.setenv("NEXUS_MODEL_OUTPUT_TOKENS_PER_HOUR", "3000")
    count = 0
    def provider(request):
        nonlocal count
        count += 1
        return provider_response(request)
    with configured(monkeypatch, provider) as client:
        assert client.post("/studio-api/respond", json=body(), headers=AUTH).status_code == 200
        assert client.post("/studio-api/respond", json=body(), headers=AUTH).status_code == 429
    assert count == 1


@pytest.mark.parametrize("name,value", [
    ("NEXUS_MODEL_MAX_CALLS_PER_HOUR", "-1"),
    ("NEXUS_MODEL_MAX_CALLS_PER_HOUR", "0"),
    ("NEXUS_MODEL_MAX_CALLS_PER_HOUR", "a"),
    ("NEXUS_MODEL_MAX_CALLS_PER_HOUR", "1000001"),
    ("NEXUS_MODEL_OUTPUT_TOKENS_PER_HOUR", ""),
    ("NEXUS_MODEL_OUTPUT_TOKENS_PER_HOUR", "100000001"),
])
def test_invalid_budget_config_fails_closed(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with configured(monkeypatch, lambda _: pytest.fail("invalid config dispatched")) as client:
        result = client.post("/studio-api/respond", json=body(), headers=AUTH)
    assert result.status_code == 503
    assert value not in result.text if value else result.status_code == 503


def test_unreviewed_or_unauthenticated_request_does_not_consume_budget(monkeypatch):
    monkeypatch.setenv("NEXUS_MODEL_MAX_CALLS_PER_HOUR", "1")
    with configured(monkeypatch, provider_response) as client:
        assert client.post("/studio-api/respond", json=body()).status_code == 401
        assert client.post("/studio-api/respond", json={**body(), "consent": False},
                           headers=AUTH).status_code == 422
        assert client.app.state.model_budget.calls == 0
        assert client.post("/studio-api/respond", json=body(), headers=AUTH).status_code == 200
        assert client.app.state.model_budget.calls == 1


def test_upstream_failure_consumes_conservative_dispatch_budget(monkeypatch):
    monkeypatch.setenv("NEXUS_MODEL_MAX_CALLS_PER_HOUR", "1")
    count = 0
    def provider(request):
        nonlocal count
        count += 1
        return httpx.Response(502)
    with configured(monkeypatch, provider) as client:
        assert client.post("/studio-api/respond", json=body(), headers=AUTH).status_code == 502
        assert client.post("/studio-api/respond", json=body(), headers=AUTH).status_code == 429
    assert count == 1


def test_budget_is_atomic_and_resets_at_monotonic_window():
    budget = model.ModelBudget()
    start = budget.started
    assert budget.reserve(10, 1, 10, now=start) == 0
    assert budget.reserve(1, 1, 10, now=start + 1) > 0
    assert budget.reserve(10, 1, 10, now=start + 3600) == 0
    assert budget.calls == 1 and budget.tokens == 10


def test_requested_output_larger_than_entire_budget_is_never_sent(monkeypatch):
    monkeypatch.setenv("NEXUS_MODEL_OUTPUT_TOKENS_PER_HOUR", "100")
    with configured(monkeypatch, lambda _: pytest.fail("no dispatch allowed")) as client:
        denied = client.post("/studio-api/respond", json=body(), headers=AUTH)
    assert denied.status_code == 429
    assert int(denied.headers["retry-after"]) >= 1
