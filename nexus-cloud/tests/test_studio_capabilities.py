"""No-egress, truth-in-capability-disclosure contract."""
from fastapi.testclient import TestClient
import pytest

import main

TOKEN = "capabilities-test-operator-token-123456789"
PATH = "/studio-api/assistant/capabilities"
AUTH = {"authorization": "Bearer " + TOKEN}


@pytest.fixture
def clean_env(monkeypatch):
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", TOKEN)
    for key in (
        "NEXUS_MODEL_URL", "NEXUS_MODEL_ID", "NEXUS_MODEL_API_KEY",
        "NEXUS_MODEL_ADAPTER", "NEXUS_MODEL_STREAMING",
        "NEXUS_MODEL_BUDGET_DIR", "NEXUS_CONNECTOR_GITHUB_REPO",
        "NEXUS_CONNECTOR_GITHUB_TOKEN", "NEXUS_CONNECTOR_RENDER_SERVICE",
        "NEXUS_CONNECTOR_RENDER_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)


def _capabilities(response):
    payload = response.json()
    assert payload["schema_version"] == 1
    assert payload["authority"] == "none"
    assert payload["tools_executed"] == 0
    assert payload["provider_contact_attempted"] is False
    assert payload["browser_runtime_verified"] is False
    assert payload["deployment_revision_verified"] is False
    return {row["id"]: row for row in payload["capabilities"]}


def test_requires_single_operator_token_and_never_caches(clean_env):
    with TestClient(main.app) as client:
        assert client.get(PATH).status_code == 401
        assert client.get(PATH, headers={"authorization": "Bearer wrong"}).status_code == 401
        r = client.get(PATH, headers=AUTH)
        assert r.status_code == 200
        assert r.headers["cache-control"] == "no-store"
        assert r.headers["x-content-type-options"] == "nosniff"
        rows = _capabilities(r)
        assert rows["model"]["readiness"] == "not_configured"
        assert rows["github"]["readiness"] == "not_configured"
        assert rows["render"]["readiness"] == "not_configured"
        assert rows["tasks"]["data_boundary"] == "local_browser_javascript_only"
        assert rows["music"]["readiness"] == "source_defined_browser_surface_not_runtime_verified"
        assert rows["remote_shell"]["readiness"] == "not_implemented_in_this_gateway"
        assert all(row["separate_user_review_required"] is True and
                   row["execution_observed"] is False for row in rows.values())
        assert TOKEN not in r.text
        assert len(rows) == len(r.json()["capabilities"])


def test_configured_provider_is_not_reported_as_live(clean_env, monkeypatch):
    monkeypatch.setenv("NEXUS_MODEL_URL", "https://provider.example/v1/chat/completions")
    monkeypatch.setenv("NEXUS_MODEL_ID", "test-provider")
    monkeypatch.setenv("NEXUS_MODEL_API_KEY", "private-provider-key")
    monkeypatch.setenv("NEXUS_MODEL_STREAMING", "1")
    monkeypatch.setenv("NEXUS_CONNECTOR_GITHUB_REPO", "example/repository")
    monkeypatch.setenv("NEXUS_CONNECTOR_GITHUB_TOKEN", "secret-github-token")
    monkeypatch.setenv("NEXUS_CONNECTOR_RENDER_SERVICE", "srv-aaaaaaaaaaaa")
    monkeypatch.setenv("NEXUS_CONNECTOR_RENDER_TOKEN", "secret-render-token")

    with TestClient(main.app) as client:
        async def deny_network(*args, **kwargs):
            pytest.fail("capability disclosure must never call providers")
        client.app.state.client.request = deny_network
        result = client.get(PATH, headers=AUTH)
        assert result.status_code == 200
        rows = _capabilities(result)
        for name in ("model", "github", "render"):
            assert rows[name]["readiness"] == "configured_not_live_verified"
        assert result.json()["model_streaming_configured"] is True
        for secret in ("private-provider-key", "secret-github-token",
                       "secret-render-token", "example/repository", "srv-aaaaaaaaaaaa"):
            assert secret not in result.text


def test_exhausted_budget_is_not_ready(clean_env, monkeypatch):
    monkeypatch.setenv("NEXUS_MODEL_URL", "https://provider.example/v1/chat/completions")
    monkeypatch.setenv("NEXUS_MODEL_ID", "test-provider")
    monkeypatch.setenv("NEXUS_MODEL_MAX_REQUESTS_PER_PROCESS", "0")
    with TestClient(main.app) as client:
        rows = _capabilities(client.get(PATH, headers=AUTH))
        assert rows["model"]["readiness"] == "local_budget_exhausted"


def test_missing_connector_credential_is_not_available(clean_env, monkeypatch):
    monkeypatch.setenv("NEXUS_CONNECTOR_GITHUB_REPO", "example/repository")
    with TestClient(main.app) as client:
        rows = _capabilities(client.get(PATH, headers=AUTH))
        assert rows["github"]["readiness"] == "not_configured"
