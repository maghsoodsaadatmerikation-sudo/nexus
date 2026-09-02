import httpx
from fastapi.testclient import TestClient

import main


def test_health_does_not_claim_epistemic_correctness() -> None:
    with TestClient(main.app) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "scope": "transport-liveness-only"}


def test_delegated_routes_fail_closed_without_bearer_token(monkeypatch) -> None:
    monkeypatch.setenv("NEXUS_CORE_URL", "https://core.example")
    with TestClient(main.app) as client:
        response = client.post("/v1/requests", json={"opaque": True})
    assert response.status_code == 401


def test_delegated_routes_fail_closed_without_core(monkeypatch) -> None:
    monkeypatch.delenv("NEXUS_CORE_URL", raising=False)
    with TestClient(main.app) as client:
        response = client.get(
            "/v1/workspaces/example",
            headers={"Authorization": "Bearer operator-token"},
        )
    assert response.status_code == 503


def test_request_body_and_202_pending_response_are_preserved(monkeypatch) -> None:
    monkeypatch.setenv("NEXUS_CORE_URL", "https://core.example")
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(
            method=request.method,
            path=request.url.path,
            body=request.content,
            authorization=request.headers["authorization"],
        )
        return httpx.Response(
            202, json={"request_id": "contract-05", "status": "pending"}
        )

    with TestClient(main.app) as client:
        original = client.app.state.client
        client.app.state.client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        )
        response = client.post(
            "/v1/requests",
            content=b'{"payload":"opaque"}',
            headers={
                "Authorization": "Bearer operator-token",
                "Content-Type": "application/json",
            },
        )
        client.app.state.client = original

    assert response.status_code == 202
    assert response.json() == {"request_id": "contract-05", "status": "pending"}
    assert seen == {
        "method": "POST",
        "path": "/v1/requests",
        "body": b'{"payload":"opaque"}',
        "authorization": "Bearer operator-token",
    }
