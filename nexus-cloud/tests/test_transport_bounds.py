"""Regression tests for bounded opaque delegation and URL fidelity."""
import gzip
from contextlib import contextmanager

import httpx
import pytest
from fastapi.testclient import TestClient

import main


class Chunks(httpx.AsyncByteStream):
    def __init__(self, *chunks):
        self.chunks = chunks
        self.closed = False
        self.read_count = 0

    async def __aiter__(self):
        for chunk in self.chunks:
            self.read_count += 1
            yield chunk

    async def aclose(self):
        self.closed = True


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


AUTH = {"Authorization": "Bearer opaque"}


def test_oversized_declared_body_never_reaches_core(monkeypatch):
    def forbidden(_):
        pytest.fail("Oversized body reached the core")
    with delegated(monkeypatch, forbidden) as client:
        response = client.post("/v1/requests", content=b"small", headers={**AUTH, "Content-Length": str(1024 * 1024 + 1)})
    assert response.status_code == 413


@pytest.mark.parametrize("value", ["-1", "abc", "+12", "1, 1"])
def test_invalid_content_length_is_rejected(monkeypatch, value):
    with delegated(monkeypatch, lambda _: pytest.fail("Invalid framing forwarded")) as client:
        response = client.post("/v1/requests", content=b"x", headers={**AUTH, "Content-Length": value})
    assert response.status_code == 400


def test_actual_stream_size_is_checked_without_declared_length(monkeypatch):
    monkeypatch.setattr(main, "MAX_REQUEST_BYTES", 8, raising=False)
    with delegated(monkeypatch, lambda _: pytest.fail("Oversized stream forwarded")) as client:
        response = client.post("/v1/requests", content=iter([b"12345", b"67890"]), headers=AUTH)
    assert response.status_code == 413


def test_response_limit_closes_upstream_and_discards_partial_body(monkeypatch):
    monkeypatch.setattr(main, "MAX_RESPONSE_BYTES", 65536, raising=False)
    stream = Chunks(b"a" * 65536, b"b" * 65536, b"never-read" * 10000)
    with delegated(monkeypatch, lambda _: httpx.Response(200, stream=stream)) as client:
        response = client.get("/v1/requests", headers=AUTH)
    assert response.status_code == 502
    assert stream.closed
    assert stream.read_count == 2
    assert "aaaa" not in response.text


def test_unexpected_compression_is_rejected_before_decoding(monkeypatch):
    monkeypatch.setattr(main, "MAX_RESPONSE_BYTES", 10, raising=False)
    stream = Chunks(gzip.compress(b"a" * 65537))
    with delegated(monkeypatch, lambda _: httpx.Response(200, headers={"content-encoding": "gzip"}, stream=stream)) as client:
        response = client.get("/v1/requests", headers=AUTH)
    assert response.status_code == 502
    assert stream.closed


def test_duplicate_query_values_are_preserved(monkeypatch):
    seen = []
    def handler(request):
        seen.extend(request.url.params.multi_items())
        return httpx.Response(200, json={"ok": True})
    with delegated(monkeypatch, handler) as client:
        assert client.get("/v1/requests?tag=a&tag=b", headers=AUTH).status_code == 200
    assert seen == [("tag", "a"), ("tag", "b")]


def test_decoded_path_cannot_inject_query_or_fragment(monkeypatch):
    seen = []
    def handler(request):
        seen.append(request.url)
        return httpx.Response(200)
    with delegated(monkeypatch, handler) as client:
        assert client.get("/v1/workspaces/a%3Fb%23c?original=yes", headers=AUTH).status_code == 200
    assert seen[0].query == b"original=yes"
    assert seen[0].fragment == ""
    assert b"a%3Fb%23c" in seen[0].raw_path


def test_redirect_is_not_followed_and_authentication_headers_survive(monkeypatch):
    calls = []
    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(307, headers={"location": "https://other.example/steal", "www-authenticate": "Bearer", "retry-after": "5"})
    with delegated(monkeypatch, handler) as client:
        response = client.get("/v1/requests", headers=AUTH)
    assert len(calls) == 1
    assert response.status_code == 307
    assert "location" not in response.headers
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.headers["retry-after"] == "5"
    assert response.headers["cache-control"] == "no-store"


def test_upstream_failure_returns_generic_error(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("private-core-address", request=request)
    with delegated(monkeypatch, handler) as client:
        response = client.get("/v1/requests", headers=AUTH)
    assert response.status_code == 503
    assert "private-core-address" not in response.text


def test_exact_body_limit_and_content_encoding_are_preserved(monkeypatch):
    monkeypatch.setattr(main, "MAX_REQUEST_BYTES", 5)
    def handler(request):
        assert request.content == b"12345"
        assert request.headers["content-encoding"] == "custom"
        assert request.headers["accept-encoding"] == "identity"
        return httpx.Response(202)
    with delegated(monkeypatch, handler) as client:
        assert client.post("/v1/requests", content=b"12345", headers={**AUTH, "Content-Encoding": "custom"}).status_code == 202


def test_slow_request_body_has_total_deadline(monkeypatch):
    import anyio
    from starlette.requests import Request
    from fastapi import HTTPException
    monkeypatch.setenv("NEXUS_CORE_URL", "https://core.example")
    monkeypatch.setattr(main, "BODY_TIMEOUT_SECONDS", 0.01)
    async def receive():
        await anyio.sleep(1)
        return {"type": "http.request", "body": b"x", "more_body": False}
    request = Request({"type": "http", "method": "POST", "path": "/v1/requests", "headers": [(b"authorization", b"Bearer opaque")]}, receive)
    async def run():
        with pytest.raises(HTTPException) as error:
            await main.delegate_to_constitutional_gateway("requests", request)
        assert error.value.status_code == 408
    anyio.run(run)


def test_slow_response_is_closed_on_deadline(monkeypatch):
    import anyio
    monkeypatch.setattr(main, "BODY_TIMEOUT_SECONDS", 0.01)
    class Slow(Chunks):
        async def __aiter__(self):
            await anyio.sleep(1)
            yield b"late"
    stream = Slow()
    with delegated(monkeypatch, lambda _: httpx.Response(200, stream=stream)) as client:
        response = client.get("/v1/requests", headers=AUTH)
    assert response.status_code == 503
    assert stream.closed
