"""Cross-edge framing regressions: neither transport may forward ambiguous bodies."""
import httpx
import pytest
from fastapi.testclient import TestClient

import main
import studio_model as model
from test_studio_model import AUTH as MODEL_AUTH, BODY as MODEL_BODY, configured
from test_transport_bounds import AUTH as CORE_AUTH, delegated


@pytest.mark.parametrize(
    "headers",
    [
        [("Authorization", "Bearer opaque"), ("Authorization", "Bearer other")],
        [("Authorization", "Bearer opaque"), ("Authorization", "Bearer opaque")],
    ],
)
def test_core_refuses_duplicate_authorization_before_delegation(monkeypatch, headers):
    with delegated(monkeypatch, lambda _: pytest.fail("Duplicate core authorization forwarded")) as c:
        response = c.get("/v1/requests", headers=headers)
        assert response.status_code == 401


@pytest.mark.parametrize(
    "headers",
    [
        [("Authorization", MODEL_AUTH["authorization"]), ("Authorization", MODEL_AUTH["authorization"])],
        [("Authorization", MODEL_AUTH["authorization"]), ("Authorization", "Bearer other")],
    ],
)
def test_model_refuses_duplicate_authorization_before_provider(monkeypatch, headers):
    with configured(monkeypatch, lambda _: pytest.fail("Duplicate model authorization forwarded")) as c:
        response = c.post("/studio-api/respond", json=MODEL_BODY, headers=headers)
        assert response.status_code == 401


@pytest.mark.parametrize(
    "headers",
    [
        [("Content-Length", "2"), ("Content-Length", "2")],
        [("Content-Length", "2"), ("Transfer-Encoding", "chunked")],
        [("Content-Length", "3")],
        [("Content-Length", "bad")],
    ],
)
def test_core_rejects_ambiguous_or_inconsistent_framing(monkeypatch, headers):
    with delegated(monkeypatch, lambda _: pytest.fail("Ambiguous core body forwarded")) as c:
        response = c.post("/v1/requests", content=b"{}", headers=[*CORE_AUTH.items(), *headers])
        assert response.status_code == 400
        assert c.app.state.gateway_limiter.borrowed_tokens == 0


@pytest.mark.parametrize(
    "headers",
    [
        [("Content-Length", "2"), ("Content-Length", "2")],
        [("Content-Length", "2"), ("Transfer-Encoding", "chunked")],
        [("Content-Length", "3")],
        [("Content-Length", "bad")],
    ],
)
def test_model_rejects_ambiguous_or_inconsistent_framing(monkeypatch, headers):
    with configured(monkeypatch, lambda _: pytest.fail("Ambiguous model body forwarded")) as c:
        response = c.post(
            "/studio-api/respond",
            content=b"{}",
            headers=[*MODEL_AUTH.items(), ("Content-Type", "application/json"), *headers],
        )
        assert response.status_code == 400
        assert c.app.state.model_limiter.borrowed_tokens == 0


def test_model_oversized_declared_body_is_rejected_without_forwarding(monkeypatch):
    with configured(monkeypatch, lambda _: pytest.fail("Oversized model body forwarded")) as c:
        response = c.post(
            "/studio-api/respond",
            content=b"{}",
            headers={**MODEL_AUTH, "Content-Type": "application/json", "Content-Length": str(model.MAX_INPUT + 1)},
        )
        assert response.status_code == 413
        assert c.app.state.model_limiter.borrowed_tokens == 0


@pytest.mark.parametrize("content_type", ["application/jsonp", "application/json-seq", "text/plain", ""])
def test_model_requires_exact_json_media_type(monkeypatch, content_type):
    with configured(monkeypatch, lambda _: pytest.fail("Unexpected media type forwarded")) as c:
        response = c.post(
            "/studio-api/respond",
            content=b"{}",
            headers={**MODEL_AUTH, "Content-Type": content_type},
        )
        assert response.status_code == 415


def test_model_refuses_duplicate_content_type(monkeypatch):
    with configured(monkeypatch, lambda _: pytest.fail("Ambiguous media type forwarded")) as c:
        response = c.post(
            "/studio-api/respond",
            content=b"{}",
            headers=[*MODEL_AUTH.items(), ("Content-Type", "application/json"), ("Content-Type", "text/plain")],
        )
        assert response.status_code == 415


def test_valid_json_charset_and_valid_core_delegation_still_work(monkeypatch):
    with configured(monkeypatch) as c:
        response = c.post(
            "/studio-api/respond",
            content=__import__("json").dumps(MODEL_BODY).encode(),
            headers={**MODEL_AUTH, "Content-Type": "application/json; charset=utf-8"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["authority"] == "none"

    with delegated(monkeypatch, lambda _: httpx.Response(202, json={"status": "pending"})) as c:
        response = c.post("/v1/requests", content=b"{}", headers=CORE_AUTH)
        assert response.status_code == 202
        assert response.json() == {"status": "pending"}


def test_model_recovers_after_rejected_frame(monkeypatch):
    with configured(monkeypatch) as c:
        rejected = c.post(
            "/studio-api/respond",
            content=b"{}",
            headers={**MODEL_AUTH, "Content-Type": "application/json", "Content-Length": "3"},
        )
        assert rejected.status_code == 400
        healthy = c.post("/studio-api/respond", json=MODEL_BODY, headers=MODEL_AUTH)
        assert healthy.status_code == 200
        assert c.app.state.model_limiter.borrowed_tokens == 0
