"""Exercise the shared admission helper with raw ASGI body events."""
import anyio
import pytest
from fastapi import HTTPException, Request

from transport_bounds import read_bounded_body


def event(body, more=False):
    return {"type": "http.request", "body": body, "more_body": more}


def read(events, headers=(), limit=8):
    pending = iter(events)

    async def receive():
        return next(pending)

    request = Request({"type": "http", "headers": list(headers)}, receive)

    async def run():
        return await read_bounded_body(
            request, max_bytes=limit, timeout_seconds=1,
            too_large_detail="Too large", timeout_detail="Timed out",
            timeout_status=408,
        )

    return anyio.run(run)


def test_declared_overrun_stops_before_another_receive():
    with pytest.raises(HTTPException) as error:
        read([event(b"ab", True), event(b"cd", True)],
             [(b"content-length", b"3")])
    assert error.value.status_code == 400
    assert error.value.detail == "Content-Length mismatch"


@pytest.mark.parametrize("headers", [[], [(b"content-length", b"3")]])
def test_disconnect_discards_partial_body(headers):
    with pytest.raises(HTTPException) as error:
        read([event(b"a", True), {"type": "http.disconnect"}], headers)
    assert error.value.status_code == 400
    assert error.value.detail == "Incomplete request body"


def test_disconnect_after_declared_length_is_not_success():
    with pytest.raises(HTTPException) as error:
        read([event(b"abc", True), {"type": "http.disconnect"}],
             [(b"content-length", b"3")])
    assert error.value.status_code == 400


def test_short_complete_body_is_rejected():
    with pytest.raises(HTTPException) as error:
        read([event(b"ab")], [(b"content-length", b"3")])
    assert error.value.status_code == 400


def test_global_limit_takes_precedence():
    with pytest.raises(HTTPException) as error:
        read([event(b"123456789", True)], [(b"content-length", b"3")])
    assert error.value.status_code == 413


@pytest.mark.parametrize("headers", [[], [(b"content-length", b"8")]])
def test_exact_limit_with_terminal_empty_event(headers):
    assert read([event(b"1234", True), event(b"5678", True), event(b"")],
                headers) == b"12345678"
