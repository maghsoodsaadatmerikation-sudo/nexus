from contextlib import contextmanager
import base64

import httpx
import pytest
from fastapi.testclient import TestClient

import main
from studio_connections import target_id, git_blob_sha

def followup_fixture(operation, outcome, revision, file_bytes_verified=False):
    return {
        "schema_version": 1,
        "kind": "github_followup_read",
        "operation": operation,
        "outcome": outcome,
        "revision": revision,
        "followup_read_verified": True,
        "reviewed_request_matched": True,
        "file_bytes_verified": file_bytes_verified,
        "independent_attestation": False,
        "deployment_verified": False,
    }


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
        return httpx.Response(200, json={"type": "file", "encoding": "base64", "sha": "2fff7e03e4b1b357ff55ef2a36fb232441fd6052",
                                       "path": "docs/intro.md", "content": base64.b64encode(source.encode()).decode(),
                                       "unreviewed": "internal details"})
    with gateway(monkeypatch, handler) as client:
        result = client.post("/studio-api/connections/read", headers=AUTH,
                             json=read_body(path="docs/intro.md", revision="b" * 40))
        assert result.status_code == 200
        assert result.json()["result"] == {"path": "docs/intro.md", "blob_sha": "2fff7e03e4b1b357ff55ef2a36fb232441fd6052", "text": source}
        assert result.json()["provenance"] == "external-untrusted"
        assert "internal details" not in result.text



def test_github_file_rejects_content_that_does_not_match_its_blob_id(monkeypatch):
    """An external response must not label altered bytes with a Git blob identifier."""
    calls = []
    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={
            "type": "file", "encoding": "base64", "path": "docs/intro.md",
            # Real Git blob SHA-1 of "Hello\n", NOT the bytes supplied below.
            "sha": "e965047ad7c57865823c7d992b1d046ea66edf78",
            "content": base64.b64encode("Altered note\n".encode()).decode(),
        })
    with gateway(monkeypatch, handler) as client:
        result = client.post("/studio-api/connections/read", headers=AUTH,
                             json=read_body(path="docs/intro.md", revision="b" * 40))
        assert result.status_code == 502
        assert result.json()["detail"] == "Provider result is not supported text or metadata"
        assert "Altered note" not in result.text
        assert calls == ["/repos/example/nexus/contents/docs/intro.md"]


def test_github_blob_identity_covers_exact_line_endings(monkeypatch):
    source = "Hello\r\n"
    import hashlib
    raw = source.encode("utf-8")
    expected = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + bytes([0]) + raw).hexdigest()
    def handler(request):
        return httpx.Response(200, json={"type": "file", "encoding": "base64",
            "path": "docs/intro.md", "sha": expected,
            "content": base64.b64encode(raw).decode()})
    with gateway(monkeypatch, handler) as client:
        result = client.post("/studio-api/connections/read", headers=AUTH,
                             json=read_body(path="docs/intro.md"))
        assert result.status_code == 200, result.text
        assert result.json()["result"]["blob_sha"] == expected
        assert result.json()["result"]["text"] == source
        assert result.json()["provenance"] == "external-untrusted"


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
        if request.url.path.endswith("/branches/" + TOPIC):
            return httpx.Response(200, json={"name": TOPIC, "commit": {"sha": BASE_SHA}})
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
        assert result.status_code == 200
        assert result.json()["target"] == REPO
        assert result.json()["status"] == "created"
        assert result.json()["receipt"] == followup_fixture("github.branch", "created", BASE_SHA)
        already = client.post(BRANCH_WRITE, headers=AUTH, json=data)
        assert already.status_code == 200 and already.json()["status"] == "already_exists"
        assert already.json()["receipt"] == followup_fixture("github.branch", "already_exists", BASE_SHA)
        existing = {**ref, "object": {"type": "commit", "sha": "b" * 40}}
        assert client.post(BRANCH_WRITE, headers=AUTH, json=data).status_code == 409
        assert methods.count("POST") == 1
        assert methods.count("GET") >= 5


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


FILE_BASE = "/studio-api/connections/github/file-base"
FILE_PREVIEW = "/studio-api/connections/github/file-preview"
FILE_COMMIT = "/studio-api/connections/github/file-commit"
FILE_PATH = "docs/intro.md"


def test_reviewed_file_edit_is_bound_to_text_and_atomic_head(monkeypatch):
    import json

    monkeypatch.setenv("NEXUS_CONNECTOR_GITHUB_FILE_TOKEN", "dedicated-file-token")
    calls = []
    old = "Hello\n"
    new = "Hello, Studio\n"
    old_blob = "e965047ad7c57865823c7d992b1d046ea66edf78"
    new_blob = git_blob_sha(new.encode())
    current = BASE_SHA

    def provider(request):
        nonlocal current
        calls.append((request.method, request.url.path))
        assert request.url.host == "api.github.com"
        assert request.headers["authorization"] == "Bearer dedicated-file-token"
        path = request.url.path
        if path.endswith("/branches/" + TOPIC):
            return httpx.Response(200, json={"name": TOPIC, "commit": {"sha": current}})
        if path.endswith("/git/commits/" + BASE_SHA):
            return httpx.Response(200, json={"sha": BASE_SHA, "tree": {"sha": "b" * 40}})
        if path.endswith("/git/commits/" + "e" * 40):
            return httpx.Response(200, json={"sha": "e" * 40, "tree": {"sha": "c" * 40}})
        if path.endswith("/git/trees/" + "b" * 40):
            return httpx.Response(200, json={"truncated": False, "tree": [
                {"path": FILE_PATH, "mode": "100644", "type": "blob", "sha": old_blob},
                {"path": "docs/link.md", "mode": "120000", "type": "blob", "sha": "d" * 40},
            ]})
        if path.endswith("/git/trees/" + "c" * 40):
            return httpx.Response(200, json={"truncated": False, "tree": [
                {"path": FILE_PATH, "mode": "100644", "type": "blob", "sha": new_blob},
            ]})
        if path.endswith("/contents/" + FILE_PATH):
            ref = request.url.params["ref"]
            assert ref in {BASE_SHA, "e" * 40}
            text = new if ref == "e" * 40 else old
            blob = new_blob if ref == "e" * 40 else old_blob
            return httpx.Response(200, json={"type": "file", "path": FILE_PATH, "encoding": "base64",
                                             "sha": blob, "content": base64.b64encode(text.encode()).decode()})
        assert request.method == "POST" and path == "/graphql"
        data = json.loads(request.content)["variables"]["input"]
        assert data["branch"] == {"repositoryNameWithOwner": REPO, "branchName": TOPIC}
        assert data["expectedHeadOid"] == BASE_SHA
        assert data["fileChanges"] == {"additions": [{"path": FILE_PATH,
                                                        "contents": base64.b64encode(new.encode()).decode()}]}
        if current != data["expectedHeadOid"]:
            return httpx.Response(200, json={"errors": [{"message": "Head changed"}], "data": {}})
        current = "e" * 40
        return httpx.Response(200, json={"data": {"createCommitOnBranch": {"commit": {"oid": current}}}})

    with gateway(monkeypatch, provider) as client:
        target = {**branch_input(), "path": FILE_PATH}
        res = client.post(FILE_BASE, headers=AUTH, json=target)
        assert res.status_code == 200 and res.json()["text"] == old
        assert client.post(FILE_BASE, headers=AUTH, json={**target, "path": "docs/link.md"}).status_code == 422
        assert client.post(FILE_BASE, headers=AUTH, json={**target, "path": ".github/check.py"}).status_code == 422
        draft = {**target, "base_sha": BASE_SHA, "text": new}
        p = client.post(FILE_PREVIEW, headers=AUTH, json=draft).json()
        assert "-Hello\n+Hello, Studio\n" in p["diff"]
        approval_body = {**draft, "consent": True, "review_id": p["review_id"], "expires_at": p["expires_at"]}
        assert client.post(FILE_COMMIT, headers=AUTH, json={**approval_body, "text": "Changed after review"}).status_code == 409
        assert client.post(FILE_COMMIT, headers=AUTH, json={**approval_body, "consent": False}).status_code == 422
        assert all(method == "GET" for method, _ in calls)
        written = client.post(FILE_COMMIT, headers=AUTH, json=approval_body)
        assert written.status_code == 200 and written.json()["commit"] == "e" * 40
        assert written.json()["receipt"] == followup_fixture("github.file_commit", "committed", "e" * 40,
                                                              file_bytes_verified=True)
        assert any(path.endswith("/git/commits/" + "e" * 40) for _, path in calls)
        assert any(path.endswith("/git/trees/" + "c" * 40) for _, path in calls)
        assert client.post(FILE_COMMIT, headers=AUTH, json=approval_body).status_code == 409
        assert client.post(FILE_PREVIEW, headers=AUTH, json=draft).status_code == 409


def test_branch_write_post_echo_without_matching_followup_read_is_not_a_receipt(monkeypatch):
    monkeypatch.setenv("NEXUS_CONNECTOR_GITHUB_BRANCH_TOKEN", "branch-review-token-synthetic")
    posts = []
    ref = {"ref": "refs/heads/" + TOPIC,
           "object": {"sha": BASE_SHA, "type": "commit"}}

    def provider(request):
        if request.url.path.endswith("/branches/main"):
            return httpx.Response(200, json={"name": "main", "commit": {"sha": BASE_SHA}})
        if request.url.path.endswith("/git/ref/heads/" + TOPIC):
            return httpx.Response(404)
        if request.url.path.endswith("/git/refs"):
            posts.append(request)
            return httpx.Response(201, json=ref)
        if request.url.path.endswith("/branches/" + TOPIC):
            # A matching POST echo is insufficient when the branch points
            # somewhere other than the exact reviewed base SHA.
            return httpx.Response(200, json={"name": TOPIC, "commit": {"sha": "f" * 40}})
        pytest.fail("Unexpected provider operation " + request.url.path)

    with gateway(monkeypatch, provider) as client:
        data = approval(client)
        result = client.post(BRANCH_WRITE, headers=AUTH, json=data)
        assert result.status_code == 502
        assert "outcome unknown" in result.json()["detail"]
        assert "receipt" not in result.json()
        assert len(posts) == 1


def test_file_write_post_echo_without_reviewed_bytes_is_not_a_receipt(monkeypatch):
    import json

    monkeypatch.setenv("NEXUS_CONNECTOR_GITHUB_FILE_TOKEN", "dedicated-synthetic-file-token")
    current = BASE_SHA
    old, replacement = "Before\\n", "After\\n"
    old_blob = git_blob_sha(old.encode())
    commit = "e" * 40
    writes = []

    def provider(request):
        nonlocal current
        path = request.url.path
        if path.endswith("/branches/" + TOPIC):
            return httpx.Response(200, json={"name": TOPIC, "commit": {"sha": current}})
        if path.endswith("/git/commits/" + BASE_SHA):
            return httpx.Response(200, json={"sha": BASE_SHA, "tree": {"sha": "b" * 40}})
        if path.endswith("/git/commits/" + commit):
            return httpx.Response(200, json={"sha": commit, "tree": {"sha": "c" * 40}})
        if path.endswith("/git/trees/" + "b" * 40) or path.endswith("/git/trees/" + "c" * 40):
            return httpx.Response(200, json={"truncated": False, "tree": [
                {"path": FILE_PATH, "mode": "100644", "type": "blob", "sha": old_blob},
            ]})
        if path.endswith("/contents/" + FILE_PATH):
            assert request.url.params["ref"] in (BASE_SHA, commit)
            return httpx.Response(200, json={"type": "file", "path": FILE_PATH,
                                              "encoding": "base64", "sha": old_blob,
                                              "content": base64.b64encode(old.encode()).decode()})
        if path == "/graphql" and request.method == "POST":
            mutation = json.loads(request.content)["variables"]["input"]
            assert mutation["fileChanges"]["additions"][0]["contents"] == base64.b64encode(replacement.encode()).decode()
            writes.append(mutation)
            current = commit
            return httpx.Response(200, json={"data": {"createCommitOnBranch": {"commit": {"oid": commit}}}})
        pytest.fail("Unexpected provider operation " + path)

    with gateway(monkeypatch, provider) as client:
        draft = {**branch_input(), "path": FILE_PATH, "base_sha": BASE_SHA, "text": replacement}
        preview = client.post(FILE_PREVIEW, headers=AUTH, json=draft)
        assert preview.status_code == 200
        reviewed = {**draft, "consent": True, "review_id": preview.json()["review_id"],
                    "expires_at": preview.json()["expires_at"]}
        outcome = client.post(FILE_COMMIT, headers=AUTH, json=reviewed)
        assert outcome.status_code == 502
        assert "outcome unknown" in outcome.json()["detail"]
        assert "receipt" not in outcome.json()
        assert len(writes) == 1
