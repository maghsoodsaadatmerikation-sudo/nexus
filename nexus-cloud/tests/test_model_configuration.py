"""Regression coverage for immutable, consent-bound Studio model configuration."""
import json

import httpx
from fastapi.testclient import TestClient

import main
import studio_model as model
from model_configuration import read_model_config
from test_studio_model import AUTH, BODY, TOKEN, configured


def test_configuration_is_immutable_and_redacts_secrets_from_repr():
    values = {
        "NEXUS_MODEL_URL": "https://provider.example/v1/chat/completions",
        "NEXUS_MODEL_ID": "reviewed-model",
        "NEXUS_MODEL_ADAPTER": "generic",
        "NEXUS_STUDIO_TOKEN": TOKEN,
        "NEXUS_MODEL_API_KEY": "never-expose-this-provider-key",
    }
    snapshot = read_model_config(values)
    assert snapshot is not None
    values["NEXUS_MODEL_ID"] = "changed-model"
    values["NEXUS_MODEL_API_KEY"] = "rotated-provider-key"
    assert snapshot.model_id == "reviewed-model"
    assert snapshot.provider_api_key == "never-expose-this-provider-key"
    assert TOKEN not in repr(snapshot)
    assert "never-expose-this-provider-key" not in repr(snapshot)
    assert snapshot.provider_host == "provider.example"


def test_review_fingerprint_binds_policy_but_never_secrets(monkeypatch):
    with configured(monkeypatch) as client:
        snapshot = model.config()
        assert snapshot is not None
        reviewed_id = model.configuration_id(snapshot)
        assert reviewed_id == model.configuration_id((snapshot.endpoint, snapshot.model_id))
        assert reviewed_id == BODY["configuration_id"]
        assert snapshot.studio_token not in reviewed_id
        assert snapshot.provider_api_key not in reviewed_id

        original_policy = model.POLICY
        monkeypatch.setattr(model, "POLICY", original_policy + " Additional safety constraints.")
        changed_id = client.get("/studio-api/status").json()["configuration_id"]
        assert changed_id != reviewed_id
        rejected = client.post("/studio-api/respond", json=BODY, headers=AUTH)
        assert rejected.status_code == 409
        assert client.app.state.model_limiter.borrowed_tokens == 0


def test_one_request_uses_one_snapshot_even_if_environment_changes_mid_body(monkeypatch):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        seen.append((str(request.url), request.headers.get("authorization"), payload))
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "Stable response"}, "finish_reason": "stop"}]}
        )

    original_reader = model.read_bounded_body

    async def read_then_rotate(*args, **kwargs):
        body = await original_reader(*args, **kwargs)
        monkeypatch.setenv("NEXUS_MODEL_URL", "https://rotated.example/v1/chat/completions")
        monkeypatch.setenv("NEXUS_MODEL_ID", "rotated-model")
        monkeypatch.setenv("NEXUS_MODEL_ADAPTER", "deepseek")
        monkeypatch.setenv("NEXUS_MODEL_API_KEY", "rotated-key")
        return body

    monkeypatch.setattr(model, "read_bounded_body", read_then_rotate)
    with configured(monkeypatch, handler) as client:
        result = client.post("/studio-api/respond", json=BODY, headers=AUTH)
        assert result.status_code == 200, result.text
        assert result.json()["model"] == "configured-test-model"
        assert client.app.state.model_limiter.borrowed_tokens == 0

    assert len(seen) == 1
    url, authorization, payload = seen[0]
    assert url == "https://provider.example/v1/chat/completions"
    assert authorization == "Bearer provider-secret-not-for-browser"
    assert payload["model"] == "configured-test-model"
    assert "max_completion_tokens" in payload and "max_tokens" not in payload
    assert "thinking" not in payload


def test_subsequent_request_uses_new_configuration_and_requires_new_review(monkeypatch):
    with configured(monkeypatch) as client:
        monkeypatch.setenv("NEXUS_MODEL_ID", "new-model")
        monkeypatch.setenv("NEXUS_MODEL_ADAPTER", "deepseek")
        current = client.get("/studio-api/status").json()
        assert current["configuration_id"] != BODY["configuration_id"]
        assert "thinking" in current["modes"]
        assert client.post("/studio-api/respond", json=BODY, headers=AUTH).status_code == 409
