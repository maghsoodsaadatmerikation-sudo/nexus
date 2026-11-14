"""Adversarial HTTP header cardinality tests for the constitutional core proxy."""
from contextlib import contextmanager

import anyio
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

import main


@contextmanager
def delegated(monkeypatch, handler):
    monkeypatch.setenv("NEXUS_CORE_URL", "https://core.example")
    with TestClient(main.app) as client:
        original = client.app.state.client
        upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client.app.state.client = upstream
        try:
            yield client
        finally:
            client.portal.call(upstream.aclose)
            client.app.state.client = original


@pytest.mark.parametrize("headers,expected", [
    ([("authorization", "Bearer first"), ("authorization", "Bearer second")], 400),
    ([("authorization", "Bearer first"), ("authorization", "Bearer first")], 400),
    ([("authorization", "Basic invalid")], 401),
])
def test_delegation_rejects_ambiguous_or_invalid_auth(monkeypatch, headers, expected):
    with delegated(monkeypatch, lambda _: pytest.fail("ambiguous authorization reached core")) as client:
        response = client.get("/v1/requests", headers=headers)
        assert response.status_code == expected
        if expected == 400:
            assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("duplicate_field", [
    "content-length", "content-type", "content-encoding",
])
def test_duplicated_message_headers_never_reach_core(monkeypatch, duplicate_field):
    headers = [
        ("authorization", "Bearer unique"),
        ("content-type", "application/json"),
        ("content-encoding", "identity"),
        ("content-length", "2"),
    ]
    original = next(v for k, v in headers if k == duplicate_field)
    # Even two identical instances are ambiguous across HTTP intermediaries.
    headers.append((duplicate_field, original))
    with delegated(monkeypatch, lambda _: pytest.fail("ambiguous framing forwarded")) as client:
        response = client.post("/v1/requests", content=b"{}", headers=headers)
        assert response.status_code == 400, response.text
        assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("duplicate_field", [
    "content-length", "content-type", "content-encoding",
])
def test_rejection_happens_before_request_body_is_polled(monkeypatch, duplicate_field):
    monkeypatch.setenv("NEXUS_CORE_URL", "https://core.example")
    headers = [
        (b"authorization", b"Bearer opaque"),
        (b"content-length", b"1"),
        (b"content-type", b"application/json"),
        (b"content-encoding", b"identity"),
    ]
    name = duplicate_field.encode()
    headers.append((name, next(v for k, v in headers if k == name)))
    polled = []

    async def receive():
        polled.append(True)
        raise AssertionError("body was consumed before rejecting duplicate headers")

    scope = {"type": "http", "method": "POST", "path": "/v1/requests",
             "headers": headers, "app": main.app}
    request = Request(scope, receive)

    async def check():
        main.app.state.gateway_limiter = anyio.CapacityLimiter(16)
        with pytest.raises(HTTPException) as exc:
            await main.delegate_to_constitutional_gateway("requests", request)
        assert exc.value.status_code == 400

    anyio.run(check)
    assert not polled


def test_single_value_headers_and_opaque_body_are_still_forwarded(monkeypatch):
    seen = []
    def handler(request):
        seen.append(request)
        assert request.content == b'{"ok":true}'
        assert request.headers["authorization"] == "Bearer unique"
        assert request.headers["content-type"] == "application/json"
        assert request.headers["content-encoding"] == "identity"
        assert request.headers["accept-encoding"] == "identity"
        return httpx.Response(202, json={"accepted": True})
    headers = [
        ("authorization", "Bearer unique"),
        ("content-type", "application/json"),
        ("content-encoding", "identity"),
        ("content-length", "11"),
    ]
    with delegated(monkeypatch, handler) as client:
        response = client.post("/v1/requests", content=b'{"ok":true}', headers=headers)
        assert response.status_code == 202
        assert response.headers["cache-control"] == "no-store"
    assert len(seen) == 1


def test_two_authorization_headers_are_rejected_before_model_or_core(monkeypatch):
    with delegated(monkeypatch, lambda _: pytest.fail("unexpected forwarding")) as client:
        response = client.get("/v1/requests", headers=[
            ("authorization", "Bearer apparently-valid"),
            ("authorization", "Bearer other"),
        ])
        assert response.status_code == 400
