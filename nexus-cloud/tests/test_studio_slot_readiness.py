"""Read-only, authenticated per-model-slot readiness diagnostics.

All fixture identities are synthetic. No paid provider or external host is contacted.
"""
from fastapi.testclient import TestClient
import pytest

import main
import studio_model

TOKEN = "slot-readiness-studio-credential-0123456789"
AUTH = {"authorization": "Bearer " + TOKEN}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", TOKEN)
    monkeypatch.setenv("NEXUS_MODEL_URL", "https://primary.example/v1/chat/completions")
    monkeypatch.setenv("NEXUS_MODEL_ID", "synthetic-primary")
    monkeypatch.setenv("NEXUS_MODEL_ADAPTER", "generic")
    monkeypatch.setenv("NEXUS_MODEL_API_KEY", "synthetic-primary-key")
    monkeypatch.setenv("NEXUS_MODEL_MAX_REQUESTS_PER_PROCESS", "2")
    monkeypatch.delenv("NEXUS_MODEL_BUDGET_DIR", raising=False)
    monkeypatch.delenv("NEXUS_MODEL_STREAMING", raising=False)
    monkeypatch.setenv("NEXUS_MODEL_SECONDARY_URL", studio_model.ANTHROPIC_MESSAGES)
    monkeypatch.setenv("NEXUS_MODEL_SECONDARY_ID", "synthetic-secondary")
    monkeypatch.setenv("NEXUS_MODEL_SECONDARY_ADAPTER", "anthropic")
    monkeypatch.setenv("NEXUS_MODEL_SECONDARY_API_KEY", "synthetic-secondary-key")
    monkeypatch.delenv("NEXUS_MODEL_SECONDARY_STREAMING", raising=False)
    for key in ("URL", "ID", "ADAPTER", "API_KEY", "STREAMING", "WORKSPACE_ID"):
        monkeypatch.delenv("NEXUS_MODEL_TERTIARY_" + key, raising=False)
    with TestClient(main.app) as ready:
        yield ready


def test_primary_is_backward_compatible(client):
    base = client.get("/studio-api/operator-readiness", headers=AUTH)
    assert base.status_code == 200
    body = base.json()
    assert "model_slot" not in body
    assert body["model"] == "synthetic-primary"
    assert body["provider_host"] == "primary.example"
    assert body["readiness"] == "READY_TO_TEST"
    assert body["provider_live_verification"] == "NOT_RECORDED"
    assert body["provider_contact_attempted"] is False
    selected = client.get("/studio-api/operator-readiness?model_slot=primary", headers=AUTH)
    assert selected.status_code == 200
    assert selected.json() == {**body, "model_slot": "primary"}


def test_secondary_readiness_uses_its_own_provider_identity(client):
    response = client.get("/studio-api/operator-readiness?model_slot=secondary", headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert body["model_slot"] == "secondary"
    assert body["model"] == "synthetic-secondary"
    assert body["provider_host"] == "api.anthropic.com"
    assert body["adapter"] == "anthropic"
    assert body["configuration_valid"] is True
    assert body["readiness"] == "READY_TO_TEST"
    assert body["provider_live_verification"] == "NOT_RECORDED"
    assert body["provider_contact_attempted"] is False
    assert body["local_request_budget"] == {"limit": 2, "attempted": 0, "remaining": 2}
    assert "synthetic-secondary-key" not in response.text
    assert TOKEN not in response.text
    assert client.app.state.model_budget.snapshot()["attempted"] == 0


def test_missing_tertiary_does_not_inherit_primary_or_secondary(client):
    response = client.get("/studio-api/operator-readiness?model_slot=tertiary", headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert body["model_slot"] == "tertiary"
    assert body["configuration_valid"] is False
    assert body["readiness"] == "NOT_CONFIGURED"
    assert body["model"] is None
    assert body["provider_host"] is None
    assert body["adapter"] is None
    assert body["provider_contact_attempted"] is False


@pytest.mark.parametrize("suffix", [
    "?model_slot=",
    "?model_slot=ALL",
    "?model_slot=secondary&model_slot=primary",
    "?model_slot=secondary&model_slot=secondary",
    "?model_slot=primary%0A",
    "?model_slot=other",
])
def test_invalid_slot_is_rejected_without_consuming_budget(client, suffix):
    response = client.get("/studio-api/operator-readiness" + suffix, headers=AUTH)
    assert response.status_code == 422
    assert client.app.state.model_budget.snapshot()["attempted"] == 0


def test_slot_details_require_operator_authentication(client):
    path = "/studio-api/operator-readiness?model_slot=secondary"
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"authorization": "Bearer wrong"}).status_code == 401
    assert client.get(path, headers=[
        ("authorization", "Bearer " + TOKEN),
        ("authorization", "Bearer " + TOKEN)
    ]).status_code == 401


def test_invalid_secondary_configuration_is_not_reported_ready(client, monkeypatch):
    monkeypatch.setenv("NEXUS_MODEL_SECONDARY_URL", "https://evil.example/v1/messages")
    payload = client.get(
        "/studio-api/operator-readiness?model_slot=secondary", headers=AUTH
    ).json()
    assert payload["readiness"] == "NOT_CONFIGURED"
    assert payload["configuration_valid"] is False
    assert payload["provider_host"] is None
    assert payload["provider_contact_attempted"] is False
