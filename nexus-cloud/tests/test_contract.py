import httpx
import pytest
from fastapi.testclient import TestClient

import main


def test_health_does_not_claim_epistemic_correctness() -> None:
    with TestClient(main.app) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "scope": "transport-liveness-only"}


def test_service_metadata_exposes_configuration_state_not_core_location(
    monkeypatch,
) -> None:
    core_url = "https://core.example"
    monkeypatch.setenv("NEXUS_CORE_URL", core_url)
    with TestClient(main.app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "nexus-cloud-adapter",
        "status": "operational",
        "authority": "none",
        "core": "configured",
    }
    assert core_url not in response.text


def test_delegated_routes_fail_closed_without_bearer_token(monkeypatch) -> None:
    monkeypatch.setenv("NEXUS_CORE_URL", "https://core.example")
    with TestClient(main.app) as client:
        response = client.post("/v1/requests", json={"opaque": True})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_delegated_routes_fail_closed_without_core(monkeypatch) -> None:
    monkeypatch.delenv("NEXUS_CORE_URL", raising=False)
    with TestClient(main.app) as client:
        response = client.get(
            "/v1/workspaces/example",
            headers={"Authorization": "Bearer operator-token"},
        )
    assert response.status_code == 503


@pytest.mark.parametrize(
    "core_url",
    [
        "http://core.example",
        "core.example",
        "https://user:password@core.example",
        "https://core.example/prefix",
        "https://core.example?mode=unsafe",
        "https://core.example#fragment",
        "https://core example",
        "https://core.example:99999",
    ],
)
def test_core_url_rejects_insecure_or_ambiguous_upstreams(
    monkeypatch, core_url: str
) -> None:
    monkeypatch.setenv("NEXUS_CORE_URL", core_url)
    assert main._core_url() is None


def test_core_url_normalizes_trailing_slash(monkeypatch) -> None:
    monkeypatch.setenv("NEXUS_CORE_URL", "https://core.example/")
    assert main._core_url() == "https://core.example"


def test_insecure_core_configuration_blocks_delegation(monkeypatch) -> None:
    monkeypatch.setenv("NEXUS_CORE_URL", "http://core.example")
    with TestClient(main.app) as client:
        response = client.get(
            "/v1/workspaces/example",
            headers={"Authorization": "Bearer operator-token"},
        )
    assert response.status_code == 503
    assert response.json() == {
        "detail": "NEXUS constitutional core is not securely configured"
    }


def test_request_body_query_auth_and_202_pending_response_are_preserved(
    monkeypatch,
) -> None:
    monkeypatch.setenv("NEXUS_CORE_URL", "https://core.example")
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(
            method=request.method,
            url=str(request.url),
            body=request.content,
            authorization=request.headers["authorization"],
            content_type=request.headers["content-type"],
        )
        return httpx.Response(
            202,
            json={"request_id": "contract-05", "status": "pending"},
            headers={"content-type": "application/json"},
        )

    with TestClient(main.app) as client:
        original = client.app.state.client
        client.app.state.client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        )
        response = client.post(
            "/v1/requests?mode=opaque",
            content=b'{"payload":"opaque"}',
            headers={
                "Authorization": "Bearer operator-token",
                "Content-Type": "application/json",
            },
        )
        client.app.state.client = original

    assert response.status_code == 202
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"request_id": "contract-05", "status": "pending"}
    assert seen == {
        "method": "POST",
        "url": "https://core.example/v1/requests?mode=opaque",
        "body": b'{"payload":"opaque"}',
        "authorization": "Bearer operator-token",
        "content_type": "application/json",
    }
