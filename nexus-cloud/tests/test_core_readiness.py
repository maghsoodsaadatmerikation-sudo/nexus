"""Synthetic public readiness checks: no credentials, bounds and fail-closed semantics."""
from contextlib import contextmanager
import gzip

import anyio
import httpx
import pytest
from fastapi.testclient import TestClient

import main


@contextmanager
def probe(monkeypatch, handler):
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


def test_not_configured_is_unavailable_but_liveness_is_ok(monkeypatch):
    monkeypatch.delenv("NEXUS_CORE_URL", raising=False)
    with TestClient(main.app) as client:
        live = client.get("/healthz")
        ready = client.get("/core-readyz")
    assert live.status_code == 200 and live.json()["scope"] == "transport-liveness-only"
    assert ready.status_code == 503
    assert ready.json() == {"status": "unavailable", "scope": "core-readiness-only"}
    assert ready.headers["cache-control"] == "no-store"


def test_ready_requires_exact_approved_public_probe_without_forwarding_token(monkeypatch):
    seen = []
    def handler(request):
        seen.append(request)
        assert request.method == "GET"
        assert request.url == httpx.URL("https://core.example/readyz")
        assert request.headers["accept-encoding"] == "identity"
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"status": "ready"})
    with probe(monkeypatch, handler) as client:
        r = client.get("/core-readyz", headers={"Authorization": "Bearer PRIVATE_SENTINEL"})
    assert len(seen) == 1
    assert r.status_code == 200
    assert r.json() == {"status": "ready", "scope": "core-readiness-only"}
    assert r.headers["cache-control"] == "no-store"
    assert "PRIVATE_SENTINEL" not in r.text


@pytest.mark.parametrize("status,body,headers", [
    (503, b'{"status":"ready"}', {}),
    (200, b'{"status":"alive"}', {}),
    (200, b'{"status":"quarantined"}', {}),
    (200, b'{"status":true}', {}),
    (200, b'not-json', {}),
    (200, b'{"status":"ready"}' + b"x" * 600, {}),
    (200, b'{"status":"ready"}', {"content-encoding": "gzip"}),
    (200, gzip.compress(b'{"status":"ready"}'), {"content-encoding": "gzip"}),
    (200, b'{"status":"ready"}', {"content-length": "99999"}),
    (307, b"", {"location": "https://other.example/readyz"}),
])
def test_unready_ambiguous_encoded_or_oversized_probe_is_not_promoted(monkeypatch, status, body, headers):
    calls = []
    def handler(req):
        calls.append(str(req.url))
        return httpx.Response(status, content=body, headers=headers)
    with probe(monkeypatch, handler) as client:
        r = client.get("/core-readyz")
    assert r.status_code == 503
    assert r.json() == {"status": "unavailable", "scope": "core-readiness-only"}
    assert len(calls) == 1
    assert "other.example" not in str(calls)


def test_network_failure_is_generic_and_never_reveals_upstream(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("private network diagnostic", request=request)
    with probe(monkeypatch, handler) as client:
        r = client.get("/core-readyz")
    assert r.status_code == 503
    assert "private network diagnostic" not in r.text


def test_saturated_probe_returns_503_without_upstream_io(monkeypatch):
    class Busy:
        def acquire_nowait(self):
            raise anyio.WouldBlock
        def release(self):
            pytest.fail("releasing an unacquired probe slot")
    with probe(monkeypatch, lambda _: pytest.fail("probe must not run")) as client:
        client.app.state.probe_limiter = Busy()
        r = client.get("/core-readyz")
    assert r.status_code == 503
    assert r.headers["cache-control"] == "no-store"


def test_probe_failure_frees_capacity_for_next_probe(monkeypatch):
    count = 0
    def handler(_):
        nonlocal count
        count += 1
        return httpx.Response(503 if count == 1 else 200,
                              json={"status":"quarantined" if count == 1 else "ready"})
    with probe(monkeypatch, handler) as client:
        assert client.get("/core-readyz").status_code == 503
        assert client.app.state.probe_limiter.borrowed_tokens == 0
        assert client.get("/core-readyz").status_code == 200
        assert client.app.state.probe_limiter.borrowed_tokens == 0
    assert count == 2
