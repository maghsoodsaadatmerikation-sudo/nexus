"""Admission and cancellation regressions using overlapping real ASGI requests."""
import anyio
import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import ClientDisconnect, Request

import main
from test_transport_bounds import AUTH, delegated


def test_saturation_rejects_before_body_read_and_recovers(monkeypatch):
    monkeypatch.setenv("NEXUS_CORE_URL", "https://core.example")

    async def run():
        async with main.lifespan(main.app):
            main.app.state.gateway_limiter = anyio.CapacityLimiter(1)
            started = anyio.Event()
            release = anyio.Event()
            reads = []

            async def receive():
                started.set()
                await release.wait()
                return {"type": "http.request", "body": b"", "more_body": False}

            async def forbidden_receive():
                reads.append(True)
                pytest.fail("Busy gateway read a rejected body")

            def request(receiver):
                return Request({"type": "http", "method": "POST", "path": "/v1/requests",
                                "query_string": b"", "app": main.app,
                                "headers": [(b"authorization", b"Bearer opaque")]}, receiver)

            async def upstream(_):
                return httpx.Response(202, json={"status": "pending"})

            async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as mock:
                main.app.state.client = mock
                async def first():
                    result = await main.delegate_to_constitutional_gateway("requests", request(receive))
                    assert result.status_code == 202
                async with anyio.create_task_group() as tasks:
                    tasks.start_soon(first)
                    await started.wait()
                    with pytest.raises(HTTPException) as error:
                        await main.delegate_to_constitutional_gateway("requests", request(forbidden_receive))
                    assert error.value.status_code == 503
                    assert error.value.headers == {"Retry-After": "1", "Cache-Control": "no-store"}
                    assert reads == []
                    assert main.app.state.gateway_limiter.borrowed_tokens == 1
                    release.set()
                assert main.app.state.gateway_limiter.borrowed_tokens == 0
                assert (await main.delegate_to_constitutional_gateway("requests", request(receive))).status_code == 202
    anyio.run(run)


def test_header_wait_has_total_deadline_and_releases_capacity(monkeypatch):
    monkeypatch.setattr(main, "UPSTREAM_TIMEOUT_SECONDS", 0.01)
    async def upstream(_):
        await anyio.sleep(1)
        return httpx.Response(200)
    with delegated(monkeypatch, upstream) as client:
        response = client.get("/v1/requests", headers=AUTH)
        assert response.status_code == 503
        assert client.app.state.gateway_limiter.borrowed_tokens == 0
        assert "private" not in response.text


@pytest.mark.parametrize("outcome", ["invalid_body", "disconnect", "cancelled"])
def test_capacity_is_released_on_aborted_request(monkeypatch, outcome):
    monkeypatch.setenv("NEXUS_CORE_URL", "https://core.example")
    async def run():
        async with main.lifespan(main.app):
            started = anyio.Event()
            async def receive():
                started.set()
                if outcome == "disconnect":
                    return {"type": "http.disconnect"}
                await anyio.sleep_forever()
            headers = [(b"authorization", b"Bearer opaque")]
            if outcome == "invalid_body":
                headers.append((b"content-length", b"bad"))
            request = Request({"type": "http", "method": "POST", "path": "/v1/requests",
                               "app": main.app, "headers": headers}, receive)
            async def call():
                try:
                    await main.delegate_to_constitutional_gateway("requests", request)
                except (HTTPException, ClientDisconnect):
                    pass
            async with anyio.create_task_group() as tasks:
                tasks.start_soon(call)
                if outcome == "cancelled":
                    await started.wait()
                    tasks.cancel_scope.cancel()
            assert main.app.state.gateway_limiter.borrowed_tokens == 0
    anyio.run(run)
