from contextlib import contextmanager
import base64

import httpx
import pytest
from fastapi.testclient import TestClient

import main
from studio_connections import target_id

TOKEN = "synthetic-studio-token-not-used-in-production"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
REPO = "example/nexus"
SERVICE = "srv-testdeployment01"


@contextmanager
def gateway(monkeypatch, handler):
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", TOKEN)
    monkeypatch.setenv("NEXUS_CONNECTOR_GITHUB_REPO", REPO)
    monkeypatch.setenv("NEXUS_CONNECTOR_GITHUB_TOKEN", "synthetic-github-token")
    monkeypatch.setenv("NEXUS_CONNECTOR_RENDER_SERVICE", SERVICE)
    monkeypatch.setenv("NEXUS_CONNECTOR_RENDER_TOKEN", "synthetic-render-token")
    with TestClient(main.app) as client:
        original = client.app.state.client
        upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client.app.state.client = upstream
        try:
            yield client
        finally:
            client.portal.call(upstream.aclose)
            client.app.state.client = original


def read_body(operation="github.file", **extra):
    provider = operation.split(".")[0]
    return {"consent": True, "operation": operation,
            "configuration_id": target_id(provider, REPO if provider == "github" else SERVICE), **extra}


def test_catalog_is_authenticated_and_contains_no_credentials(monkeypatch):
    with gateway(monkeypatch, lambda _: pytest.fail("catalog contacted a provider")) as client:
        assert client.get("/studio-api/connections").status_code == 401
        response = client.get("/studio-api/connections", headers=AUTH)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == {"connections": [
            {"provider": "github", "target": REPO, "configuration_id": target_id("github", REPO)},
            {"provider": "render", "target": SERVICE, "configuration_id": target_id("render", SERVICE)},
        ]}
        assert "synthetic" not in response.text


def test_only_explicit_current_allowlisted_requests_reach_providers(monkeypatch):
    with gateway(monkeypatch, lambda _: pytest.fail("unreviewed request forwarded")) as client:
        endpoint = "/studio-api/connections/read"
        payload = read_body(path="docs/intro.md")
        assert client.post(endpoint, json=payload).status_code == 401
        for invalid in [
            {**payload, "consent": False}, {**payload, "consent": 1},
            {**payload, "path": "../README.md"}, {**payload, "path": "%2e%2e/README.md"},
            {**payload, "url": "https://unrelated.example"}, {**payload, "operation": "render.deploy"},
        ]:
            assert client.post(endpoint, json=invalid, headers=AUTH).status_code == 422
        monkeypatch.setenv("NEXUS_CONNECTOR_GITHUB_REPO", "example/another")
        assert client.post(endpoint, json=payload, headers=AUTH).status_code == 409


def test_github_reads_pinned_utf8_and_returns_only_reviewed_fields(monkeypatch):
    source = "گفتگو\n"
    def handler(request):
        assert request.method == "GET"
        assert request.url.host == "api.github.com"
        assert request.url.path == f"/repos/{REPO}/contents/docs/intro.md"
        assert request.url.params["ref"] == "b" * 40
        assert request.headers["authorization"] == "Bearer synthetic-github-token"
        return httpx.Response(200, json={"type": "file", "encoding": "base64", "sha": "a" * 40,
                                       "path": "docs/intro.md", "content": base64.b64encode(source.encode()).decode(),
                                       "unreviewed": "internal details"})
    with gateway(monkeypatch, handler) as client:
        result = client.post("/studio-api/connections/read", headers=AUTH,
                             json=read_body(path="docs/intro.md", revision="b" * 40))
        assert result.status_code == 200
        assert result.json()["result"] == {"path": "docs/intro.md", "blob_sha": "a" * 40, "text": source}
        assert result.json()["provenance"] == "external-untrusted"
        assert "internal details" not in result.text


def test_render_only_reads_selected_service_and_projects_deploy_metadata(monkeypatch):
    def handler(request):
        assert request.method == "GET"
        assert request.url.host == "api.render.com"
        assert request.url.path == f"/v1/services/{SERVICE}/deploys"
        assert request.headers["authorization"] == "Bearer synthetic-render-token"
        return httpx.Response(200, json=[{"deploy": {"id": "dep-test", "status": "live",
                                                     "commit": {"id": "c" * 40, "message": "private message"},
                                                     "createdAt": "2026-11-20T00:00:00Z"}}])
    with gateway(monkeypatch, handler) as client:
        result = client.post("/studio-api/connections/read", headers=AUTH, json=read_body("render.deploys"))
        assert result.status_code == 200
        assert result.json()["result"] == [{"id": "dep-test", "status": "live", "commit": "c" * 40,
                                            "created_at": "2026-11-20T00:00:00Z"}]
        assert "private message" not in result.text


def test_redirects_are_rejected_without_contacting_destination(monkeypatch):
    calls = []
    def handler(request):
        calls.append(request.url.host)
        return httpx.Response(302, headers={"Location": "https://unrelated.example/redirect"})
    with gateway(monkeypatch, handler) as client:
        result = client.post("/studio-api/connections/read", headers=AUTH, json=read_body("github.pulls"))
        assert result.status_code == 502
        assert calls == ["api.github.com"]


def test_large_github_descriptions_are_discarded_instead_of_returned(monkeypatch):
    def handler(request):
        assert request.url.params["per_page"] == "8"
        return httpx.Response(200, json=[
            {"number": i, "title": f"Draft {i}", "body": "UNREVIEWED " * 3500,
             "head": {"ref": "topic", "sha": "a" * 40}, "base": {"ref": "main"}}
            for i in range(1, 9)
        ])
    with gateway(monkeypatch, handler) as client:
        result = client.post("/studio-api/connections/read", headers=AUTH, json=read_body("github.pulls"))
        assert result.status_code == 200
        assert len(result.json()["result"]) == 8
        assert "UNREVIEWED" not in result.text


BASE_SHA = "a" * 40
TOPIC = "nexus/studio-example-change"
BRANCH_PREVIEW = "/studio-api/connections/github/branch-preview"
BRANCH_WRITE = "/studio-api/connections/github/branch"


def branch_input():
    return {"configuration_id": target_id("github", REPO), "slug": "example-change"}


def approval(client):
    response = client.post(BRANCH_PREVIEW, headers=AUTH, json=branch_input())
    assert response.status_code == 200
    p = response.json()
    assert p["target"] == REPO and p["branch"] == TOPIC
    return {**branch_input(), "consent": True,
            **{k: p[k] for k in ("base_sha", "review_id", "expires_at")}}


def test_branch_preview_and_create_require_dedicated_credential(monkeypatch):
    monkeypatch.delenv("NEXUS_CONNECTOR_GITHUB_BRANCH_TOKEN", raising=False)
    with gateway(monkeypatch, lambda _: pytest.fail("provider contacted")) as client:
        assert client.post(BRANCH_PREVIEW, headers=AUTH, json=branch_input()).status_code == 409


def test_confirmed_branch_write_never_replaces_an_existing_ref(monkeypatch):
    import json
    monkeypatch.setenv("NEXUS_CONNECTOR_GITHUB_BRANCH_TOKEN", "separate-synthetic-write-token")
    methods = []
    ref = {"ref": "refs/heads/" + TOPIC, "object": {"sha": BASE_SHA, "type": "commit"}}
    existing = None

    def provider(request):
        nonlocal existing
        methods.append(request.method)
        assert request.url.host == "api.github.com"
        assert request.headers["authorization"] == "Bearer separate-synthetic-write-token"
        if request.url.path.endswith("/branches/main"):
            return httpx.Response(200, json={"name": "main", "commit": {"sha": BASE_SHA}})
        if request.method == "GET":
            assert request.url.path.endswith("/git/ref/heads/" + TOPIC)
            return httpx.Response(200, json=existing) if existing else httpx.Response(404)
        assert request.method == "POST" and request.url.path.endswith("/git/refs")
        assert json.loads(request.content) == {"ref": ref["ref"], "sha": BASE_SHA}
        existing = ref
        return httpx.Response(201, json=ref)

    with gateway(monkeypatch, provider) as client:
        catalog = client.get("/studio-api/connections", headers=AUTH).json()
        assert catalog["connections"][0]["branch_creation"] is True
        data = approval(client)
        assert methods == ["GET"]
        for wrong_data, status in [
            ({"consent": False}, 422),
            ({"consent": 1}, 422),
            ({"slug": "../main"}, 422),
            ({"slug": "other-change"}, 409),
            ({"base_sha": "b" * 40}, 409),
            ({"expires_at": 0}, 409),
        ]:
            assert client.post(BRANCH_WRITE, headers=AUTH, json={**data, **wrong_data}).status_code == status
        assert methods == ["GET"]
        result = client.post(BRANCH_WRITE, headers=AUTH, json=data)
        assert result.json() == {"target": REPO, "branch": TOPIC, "base_sha": BASE_SHA, "status": "created"}
        assert client.post(BRANCH_WRITE, headers=AUTH, json=data).json()["status"] == "already_exists"
        existing = {**ref, "object": {"type": "commit", "sha": "b" * 40}}
        assert client.post(BRANCH_WRITE, headers=AUTH, json=data).status_code == 409
        assert methods.count("POST") == 1


def test_advanced_main_requires_a_new_preview(monkeypatch):
    monkeypatch.setenv("NEXUS_CONNECTOR_GITHUB_BRANCH_TOKEN", "separate-synthetic-write-token")
    current = BASE_SHA
    def provider(request):
        assert request.method == "GET"
        if request.url.path.endswith("/branches/main"):
            return httpx.Response(200, json={"name": "main", "commit": {"sha": current}})
        return httpx.Response(404)
    with gateway(monkeypatch, provider) as client:
        data = approval(client)
        current = "b" * 40
        assert client.post(BRANCH_WRITE, headers=AUTH, json=data).status_code == 409
