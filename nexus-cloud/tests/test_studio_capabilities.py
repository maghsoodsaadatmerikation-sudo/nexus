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
        "NEXUS_CONNECTOR_GITHUB_BRANCH_TOKEN",
        "NEXUS_CONNECTOR_GITHUB_FILE_TOKEN",
        "NEXUS_MODEL_MAX_REQUESTS_PER_PROCESS",
    ):
        monkeypatch.delenv(key, raising=False)


def _capabilities(response):
    payload = response.json()
    assert payload["schema_version"] == 2
    assert payload["authority"] == "none"
    assert payload["tools_executed"] == 0
    assert payload["provider_contact_attempted"] is False
    assert payload["browser_runtime_verified"] is False
    assert payload["deployment_revision_verified"] is False
    assert len(payload["operation_gates"]) == 9
    assert all(row["permission_verified"] is False
               and row["execution_observed"] is False
               and row["receipt_observed"] is False
               and row["separate_user_review_required"] is True
               and row["proof_boundary"] == "independent_action_receipt_required"
               for row in payload["operation_gates"])
    return {row["id"]: row for row in payload["capabilities"]}


def _gates(response):
    return {row["id"]: row for row in response.json()["operation_gates"]}


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
        gates = _gates(r)
        assert len(gates) == 9
        assert {key for key, row in gates.items() if row["potential_account_mutation"]} == {
            "github.branch", "github.file_commit"
        }
        assert all(row["configuration_readiness"] == "not_configured" for row in gates.values())
        assert gates["github.pulls"]["phase"] == "read"
        assert gates["github.branch_preview"]["phase"] == "review"
        assert gates["github.branch"]["phase"] == "write"
        assert gates["model.response"]["phase"] == "model"


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
        gates = _gates(result)
        assert gates["github.pulls"]["configuration_readiness"] == "configured_not_live_verified"
        assert gates["github.branch"]["configuration_readiness"] == "not_configured"
        assert gates["github.file_commit"]["configuration_readiness"] == "not_configured"
        assert gates["render.deploys"]["configuration_readiness"] == "configured_not_live_verified"
        assert gates["model.response"]["configuration_readiness"] == "configured_not_live_verified"
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
        assert _gates(client.get(PATH, headers=AUTH))["model.response"]["configuration_readiness"] == "local_budget_exhausted"


def test_missing_connector_credential_is_not_available(clean_env, monkeypatch):
    monkeypatch.setenv("NEXUS_CONNECTOR_GITHUB_REPO", "example/repository")
    with TestClient(main.app) as client:
        rows = _capabilities(client.get(PATH, headers=AUTH))
        assert rows["github"]["readiness"] == "not_configured"


def test_independent_github_write_credentials_do_not_prove_provider_permission(clean_env, monkeypatch):
    monkeypatch.setenv("NEXUS_CONNECTOR_GITHUB_REPO", "example/repository")
    monkeypatch.setenv("NEXUS_CONNECTOR_GITHUB_BRANCH_TOKEN", "private-branch-only-token")
    with TestClient(main.app) as client:
        async def deny_network(*args, **kwargs):
            pytest.fail("inventory cannot contact external providers")
        client.app.state.client.request = deny_network
        result = client.get(PATH, headers=AUTH)
        gates = _gates(result)
        assert gates["github.pulls"]["configuration_readiness"] == "not_configured"
        assert gates["github.branch"]["configuration_readiness"] == "configured_not_live_verified"
        assert gates["github.file_commit"]["configuration_readiness"] == "not_configured"
        assert "private-branch-only-token" not in result.text

    monkeypatch.delenv("NEXUS_CONNECTOR_GITHUB_BRANCH_TOKEN")
    monkeypatch.setenv("NEXUS_CONNECTOR_GITHUB_FILE_TOKEN", "private-file-only-token")
    with TestClient(main.app) as client:
        response = client.get(PATH, headers=AUTH)
        gates = _gates(response)
        assert gates["github.pulls"]["configuration_readiness"] == "not_configured"
        assert gates["github.branch"]["configuration_readiness"] == "not_configured"
        for name in ("github.file_base", "github.file_preview", "github.file_commit"):
            assert gates[name]["configuration_readiness"] == "configured_not_live_verified"
        assert "private-file-only-token" not in response.text


def test_unbound_write_tokens_not_reported_as_configured(clean_env, monkeypatch):
    monkeypatch.setenv("NEXUS_CONNECTOR_GITHUB_BRANCH_TOKEN", "private-branch-only-token")
    monkeypatch.setenv("NEXUS_CONNECTOR_GITHUB_FILE_TOKEN", "private-file-only-token")
    with TestClient(main.app) as client:
        result = client.get(PATH, headers=AUTH)
        assert all(row["configuration_readiness"] == "not_configured"
                   for name, row in _gates(result).items() if name.startswith("github."))
