"""Admission regressions for the public cloud adapter's delegated core pool."""
from contextlib import contextmanager

import anyio
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

import main

AUTH = {"Authorization": "Bearer synthetic-token"}


@contextmanager
def delegated(monkeypatch, handler):
    monkeypatch.setenv("NEXUS_CORE_URL", "https://core.example")
    with TestClient(main.app) as client:
        original = client.app.state.client
        replacement = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client.app.state.client = replacement
        try:
            yield client
        finally:
            client.portal.call(replacement.aclose)
            client.app.state.client = original


def test_exhausted_slots_reject_before_request_body_is_read(monkeypatch):
    """Capacity failure must be immediate even for a never-ending body."""
    monkeypatch.setenv("NEXUS_CORE_URL", "https://core.example")
    class Busy:
        def acquire_nowait(self):
            raise anyio.WouldBlock
        def release(self):
            pytest.fail("A rejected request must not release an unacquired slot")

    async def receive():
        pytest.fail("No request body may be consumed once capacity is exhausted")
    async def run():
        # Direct ASGI request makes the no-body-read property observable.
        request = Request(
            {"type": "http", "app": main.app, "method": "POST",
             "path": "/v1/requests",
             "headers": [(b"authorization", b"Bearer synthetic-token")]},
            receive,
        )
        with pytest.raises(HTTPException) as exc:
            await main.delegate_to_constitutional_gateway("requests", request)
        assert exc.value.status_code == 429
        assert exc.value.headers == {"Retry-After": "1", "Cache-Control": "no-store"}

    original = getattr(main.app.state, "core_limiter", None)
    main.app.state.core_limiter = Busy()
    try:
        anyio.run(run)
    finally:
        main.app.state.core_limiter = original


def test_success_releases_core_slot(monkeypatch):
    def handler(_):
        return httpx.Response(202, json={"status": "pending"})
    with delegated(monkeypatch, handler) as client:
        limiter = client.app.state.core_limiter
        before = limiter.borrowed_tokens
        result = client.post("/v1/requests", json={"value": 1}, headers=AUTH)
        assert result.status_code == 202
        assert limiter.borrowed_tokens == before


def test_upstream_failure_releases_core_slot(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("synthetic failure", request=request)
    with delegated(monkeypatch, handler) as client:
        limiter = client.app.state.core_limiter
        result = client.get("/v1/requests/a", headers=AUTH)
        assert result.status_code == 503
        assert limiter.borrowed_tokens == 0


def test_oversize_response_releases_core_slot(monkeypatch):
    monkeypatch.setattr(main, "MAX_RESPONSE_BYTES", 3)
    with delegated(monkeypatch, lambda _: httpx.Response(200, content=b"long")) as client:
        limiter = client.app.state.core_limiter
        result = client.get("/v1/requests/a", headers=AUTH)
        assert result.status_code == 502
        assert limiter.borrowed_tokens == 0


def test_bad_auth_does_not_consume_core_slot(monkeypatch):
    with delegated(monkeypatch, lambda _: pytest.fail("No upstream call allowed")) as client:
        limiter = client.app.state.core_limiter
        result = client.get("/v1/requests/a")
        assert result.status_code == 401
        assert limiter.borrowed_tokens == 0
