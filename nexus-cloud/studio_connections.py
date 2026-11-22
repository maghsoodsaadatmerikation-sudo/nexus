"""Operator-configured connections with reviewed operations for the Studio workspace."""

import base64
import binascii
import difflib
import hashlib
import hmac
import json
import os
import re
import time
from urllib.parse import quote

import anyio
import httpx
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing import Literal

from transport_bounds import read_bounded_body

MAX_SOURCE = 24 * 1024
MAX_RESPONSE = 128 * 1024
MAX_PULL_RESPONSE = 1024 * 1024
NO_STORE = {"Cache-Control": "no-store"}
REPO = re.compile(r"[A-Za-z0-9-]{1,39}/[A-Za-z0-9_.-]{1,100}")
SHA = r"^[a-f0-9]{40}$"
BRANCH_SLUG = r"^[a-z0-9](?:[a-z0-9-]{1,46})[a-z0-9]$"
BRANCH_PREFIX = "nexus/studio-"
REVIEW_SECONDS = 300
MAX_FILE_REQUEST = 160 * 1024
MAX_DIFF = 58 * 1024
MAX_EDIT_LINES = 1800
FILE_EXTENSIONS = {".md", ".txt", ".py", ".rs", ".js", ".mjs", ".css", ".html", ".toml", ".json"}
COMMIT_QUERY = """
mutation($input: CreateCommitOnBranchInput!) {
  createCommitOnBranch(input: $input) { commit { oid } }
}
"""
SERVICE = re.compile(r"srv-[a-z0-9]{10,40}")
OPERATIONS = {
    "github.pulls": "github",
    "github.file": "github",
    "render.deploys": "render",
}


class ReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    consent: bool
    operation: Literal["github.pulls", "github.file", "render.deploys"]
    configuration_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    path: str = Field(default="", max_length=300)
    revision: str = Field(default="", pattern=r"^(?:[a-f0-9]{40})?$")


class BranchPreview(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    configuration_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    slug: str = Field(pattern=BRANCH_SLUG)


class BranchApproval(BranchPreview):
    consent: bool
    base_sha: str = Field(pattern=SHA)
    expires_at: int
    review_id: str = Field(pattern=r"^[a-f0-9]{64}$")


class FileTarget(BranchPreview):
    path: str = Field(min_length=1, max_length=240)


class FileDraft(FileTarget):
    base_sha: str = Field(pattern=SHA)
    text: str = Field(max_length=MAX_SOURCE)


class FileApproval(FileDraft):
    consent: bool
    expires_at: int
    review_id: str = Field(pattern=r"^[a-f0-9]{64}$")


def operator_auth(request: Request):
    token = os.getenv("NEXUS_STUDIO_TOKEN", "").strip()
    if len(token) < 32:
        raise HTTPException(503, "Studio connections are not configured", headers=NO_STORE)
    values = request.headers.getlist("authorization")
    if len(values) != 1 or not hmac.compare_digest(values[0].encode(), ("Bearer " + token).encode()):
        raise HTTPException(401, "Studio authentication required",
                            headers={**NO_STORE, "WWW-Authenticate": "Bearer"})


def configured():
    github = os.getenv("NEXUS_CONNECTOR_GITHUB_REPO", "").strip()
    render = os.getenv("NEXUS_CONNECTOR_RENDER_SERVICE", "").strip()
    targets = {}
    if REPO.fullmatch(github) and github.split("/")[1] not in {".", ".."}:
        targets["github"] = (github, os.getenv("NEXUS_CONNECTOR_GITHUB_TOKEN", "").strip())
    render_token = os.getenv("NEXUS_CONNECTOR_RENDER_TOKEN", "").strip()
    if SERVICE.fullmatch(render) and render_token:
        targets["render"] = (render, render_token)
    return targets


def target_id(provider, target):
    return hashlib.sha256(f"{provider}:{target}".encode()).hexdigest()


def provider_request(data, target):
    if data.operation == "render.deploys":
        return f"https://api.render.com/v1/services/{target}/deploys", {"limit": 8}
    base = f"https://api.github.com/repos/{target}"
    if data.operation == "github.pulls":
        return base + "/pulls", {"state": "open", "per_page": 8}
    segments = data.path.split("/")
    if any(not part or part in {".", ".."} for part in segments) or any(
        c in data.path for c in ("\\", "%", "?", "#")
    ) or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in data.path):
        raise HTTPException(422, "Use a repository-relative file path")
    params = {"ref": data.revision} if data.revision else {}
    return base + "/contents/" + quote(data.path, safe="/"), params


def text_value(value, limit=240):
    if not isinstance(value, str):
        return ""
    return value[:limit].encode("utf-8", errors="replace").decode()


def git_blob_sha(content: bytes) -> str:
    """Compute Git's SHA-1 blob object ID (identity check, not a trust signature)."""
    return hashlib.sha1(b"blob " + str(len(content)).encode("ascii") + bytes([0]) + content).hexdigest()


def project_result(operation, raw, path):
    if operation == "github.file":
        if raw["type"] != "file" or raw["encoding"] != "base64" or raw["path"] != path:
            raise ValueError("expected text file")
        blob = raw["sha"]
        if not isinstance(blob, str) or not re.fullmatch(r"[a-f0-9]{40}", blob):
            raise ValueError("missing blob identifier")
        content = base64.b64decode(raw["content"].replace("\n", ""), validate=True)
        if len(content) > MAX_SOURCE or b"\x00" in content:
            raise ValueError("unsupported source")
        if git_blob_sha(content) != blob:
            raise ValueError("Git blob identifier does not match supplied bytes")
        return {"path": path, "blob_sha": blob, "text": content.decode("utf-8")}
    if not isinstance(raw, list):
        raise ValueError("expected list")
    if operation == "github.pulls":
        if any(type(row["number"]) is not int or row["number"] < 1 for row in raw[:8]):
            raise ValueError("missing pull request number")
        return [{"number": row["number"], "title": text_value(row.get("title")),
                 "head": text_value(row["head"]["ref"]), "head_sha": text_value(row["head"]["sha"], 40),
                 "base": text_value(row["base"]["ref"]), "updated_at": text_value(row.get("updated_at"), 40)}
                for row in raw[:8]]
    return [{"id": text_value(row["deploy"]["id"], 80),
             "status": text_value(row["deploy"]["status"], 50),
             "commit": text_value((row["deploy"].get("commit") or {}).get("id"), 40),
             "created_at": text_value(row["deploy"].get("createdAt"), 48)}
            for row in raw[:8]]


async def provider_json(client, provider, token, url, *, params=None, payload=None,
                        limit=MAX_RESPONSE, post_status=201):
    headers = {"accept": "application/json", "accept-encoding": "identity"}
    if provider == "github":
        headers.update({"accept": "application/vnd.github+json", "x-github-api-version": "2022-11-28"})
    if token:
        headers["authorization"] = "Bearer " + token
    body = bytearray()
    try:
        with anyio.fail_after(12):
            async with client.stream("GET" if payload is None else "POST", url, params=params,
                                     json=payload, headers=headers, follow_redirects=False) as reply:
                if reply.status_code in {401, 403}:
                    raise HTTPException(502, "Provider access was denied")
                if reply.status_code == 404:
                    raise HTTPException(404, "Provider resource is unavailable")
                if payload is not None and reply.status_code in {409, 422}:
                    raise HTTPException(409, "Provider rejected the reviewed change")
                expected_status = 200 if payload is None else post_status
                if reply.status_code != expected_status or reply.headers.get("content-encoding", "identity").lower() != "identity":
                    raise HTTPException(502, "Provider did not return a supported response")
                async for chunk in reply.aiter_bytes(chunk_size=8192):
                    if len(body) + len(chunk) > limit:
                        raise HTTPException(502, "Provider response exceeded the limit")
                    body.extend(chunk)
    except (httpx.RequestError, TimeoutError):
        raise HTTPException(504, "Provider did not respond in time") from None
    try:
        return json.loads(body)
    except (ValueError, RecursionError):
        raise HTTPException(502, "Provider returned invalid JSON") from None


async def read_provider(client, data, provider, target, token):
    url, params = provider_request(data, target)
    # GitHub includes each full PR description even though Studio only needs metadata.
    limit = MAX_PULL_RESPONSE if data.operation == "github.pulls" else MAX_RESPONSE
    raw = await provider_json(client, provider, token, url, params=params, limit=limit)
    try:
        return project_result(data.operation, raw, data.path)
    except (ValueError, KeyError, AttributeError, TypeError, RecursionError, binascii.Error):
        raise HTTPException(502, "Provider result is not supported text or metadata") from None



async def parse_request(request, schema, max_bytes=4096):
    operator_auth(request)
    media = request.headers.getlist("content-type")
    if len(media) != 1 or media[0].split(";", 1)[0].strip().lower() != "application/json":
        raise HTTPException(415, "JSON required", headers=NO_STORE)
    raw = await read_bounded_body(request, max_bytes=max_bytes, timeout_seconds=6,
                                  too_large_detail="Connection request too large",
                                  timeout_detail="Connection request timed out", timeout_status=408)
    try:
        return schema.model_validate_json(raw)
    except ValidationError:
        raise HTTPException(422, "Invalid connection request", headers=NO_STORE) from None


def take_capacity(request):
    limiter = request.app.state.connections_limiter
    try:
        limiter.acquire_nowait()
    except anyio.WouldBlock:
        raise HTTPException(429, "Connections are busy", headers=NO_STORE) from None
    return limiter


def write_config(configuration_id, setting):
    entry = configured().get("github")
    token = os.getenv(setting, "").strip()
    if not entry or not token or configuration_id != target_id("github", entry[0]):
        raise HTTPException(409, "GitHub write access is disabled or the connection changed", headers=NO_STORE)
    return entry[0], token


def branch_review_id(token, target, slug, sha, expires):
    payload = f"studio-create-branch-v1\n{target}\n{slug}\n{sha}\n{expires}"
    return hmac.new(token.encode(), payload.encode(), hashlib.sha256).hexdigest()


async def branch_head(client, target, token, branch):
    result = await provider_json(client, "github", token,
                                 f"https://api.github.com/repos/{target}/branches/{quote(branch, safe='')}")
    try:
        sha = result["commit"]["sha"]
        if result["name"] != branch or not re.fullmatch(SHA, sha):
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise HTTPException(502, "GitHub did not identify the requested branch") from None
    return sha


def editable_path(path):
    tail = path.rsplit("/", 1)[-1]
    if any(not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", part) for part in path.split("/")) \
       or "." + tail.rsplit(".", 1)[-1] not in FILE_EXTENSIONS or "." not in tail:
        raise HTTPException(422, "Choose an existing supported text file outside hidden directories", headers=NO_STORE)


def editable_text(text):
    try:
        raw = text.encode("utf-8")
    except UnicodeError:
        raise HTTPException(422, "Valid UTF-8 text is required", headers=NO_STORE) from None
    if len(raw) > MAX_SOURCE or len(text.splitlines()) > MAX_EDIT_LINES or any(c < 32 and c not in (9, 10) for c in raw):
        raise HTTPException(422, "Use LF text up to 24 KiB and 1800 lines", headers=NO_STORE)
    return raw


async def editable_file(client, target, token, sha, path):
    base = f"https://api.github.com/repos/{target}"
    # Verify that GitHub is serving a normal file at this exact path. The
    # Contents endpoint by itself can dereference a repository symlink.
    try:
        commit = await provider_json(client, "github", token, base + "/git/commits/" + sha)
        tree_sha = commit["tree"]["sha"]
        if commit["sha"] != sha or not re.fullmatch(SHA, tree_sha):
            raise ValueError()
        tree = await provider_json(client, "github", token, base + "/git/trees/" + tree_sha,
                                   params={"recursive": "1"}, limit=MAX_PULL_RESPONSE)
        if tree["truncated"] is not False or not isinstance(tree["tree"], list):
            raise ValueError()
        entry = next((row for row in tree["tree"] if row["path"] == path), None)
        if not entry or entry["mode"] != "100644" or entry["type"] != "blob":
            raise HTTPException(422, "Select an existing regular, non-executable file", headers=NO_STORE)
        raw = await provider_json(client, "github", token, base + "/contents/" + quote(path, safe="/"),
                                  params={"ref": sha})
        found = project_result("github.file", raw, path)
        if found["blob_sha"] != entry["sha"]:
            raise ValueError()
    except (ValueError, KeyError, TypeError, AttributeError, binascii.Error):
        raise HTTPException(502, "GitHub did not return a verifiable file", headers=NO_STORE) from None
    editable_text(found["text"])
    return found["text"]


def file_review_id(token, target, data, expires, raw):
    payload = json.dumps(["studio-commit-file-v1", target, data.slug, data.path, data.base_sha,
                          hashlib.sha256(raw).hexdigest(), expires], separators=(",", ":"))
    return hmac.new(token.encode(), payload.encode(), hashlib.sha256).hexdigest()


def preview_diff(previous, replacement):
    # Line feeds are retained so a final-newline edit has an explicit marker.
    changes = difflib.unified_diff(previous.splitlines(keepends=True), replacement.splitlines(keepends=True),
                                   fromfile="Before", tofile="After", n=2)
    diff = "".join(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n" for line in changes)
    if not diff or len(diff.encode()) > MAX_DIFF:
        raise HTTPException(422, "No change or the diff is too large", headers=NO_STORE)
    return diff

def write_observation_receipt(operation: str, outcome: str, observation: str) -> dict:
    """A fresh provider response is evidence, not independent signed attestation.

    Returned only after comparing a separate provider read with the exact
    reviewed write. This contains no account credentials or user text.
    """
    return {
        "schema_version": 1,
        "scope": "single_reviewed_connection_operation",
        "operation": operation,
        "outcome": outcome,
        "verification": observation,
        "confirmed_by_followup_provider_read": True,
        "independent_attestation": False,
        "deployment_verified": False,
        "authority": "none",
    }


def unconfirmed_write() -> HTTPException:
    # A write can succeed upstream and still lose its acknowledgement, or
    # fail the later observation. Never claim the absence of a mutation.
    return HTTPException(
        409,
        "Write outcome unconfirmed after provider contact; inspect the remote "
        "branch before attempting another change",
        headers=NO_STORE,
    )


def verified_ref(raw: dict, expected_ref: str, expected_sha: str) -> bool:
    try:
        return (type(raw) is dict and raw["ref"] == expected_ref
                and raw["object"]["type"] == "commit"
                and raw["object"]["sha"] == expected_sha)
    except (TypeError, KeyError):
        return False


def register(app):
    @app.get("/studio-api/connections")
    async def catalog(request: Request):
        operator_auth(request)
        targets = configured()
        return JSONResponse({"connections": [
            {"provider": provider, "target": target, "configuration_id": target_id(provider, target),
             **({"branch_creation": True} if provider == "github" and
                os.getenv("NEXUS_CONNECTOR_GITHUB_BRANCH_TOKEN", "").strip() else {}),
             **({"file_commit": True} if provider == "github" and
                os.getenv("NEXUS_CONNECTOR_GITHUB_FILE_TOKEN", "").strip() else {})}
            for provider, (target, _) in targets.items()
        ]}, headers=NO_STORE)

    @app.post("/studio-api/connections/read")
    async def read(request: Request):
        data = await parse_request(request, ReadRequest)
        if not data.consent or (data.operation != "github.file" and (data.path or data.revision)):
            raise HTTPException(422, "Review the exact connection request", headers=NO_STORE)
        provider = OPERATIONS[data.operation]
        entry = configured().get(provider)
        if entry is None or data.configuration_id != target_id(provider, entry[0]):
            raise HTTPException(409, "Connection changed or is disabled", headers=NO_STORE)
        limiter = take_capacity(request)
        try:
            result = await read_provider(request.app.state.client, data, provider, *entry)
        finally:
            limiter.release()
        return JSONResponse({"provider": provider, "target": entry[0], "operation": data.operation,
                             "provenance": "external-untrusted", "result": result}, headers=NO_STORE)

    @app.post("/studio-api/connections/github/branch-preview")
    async def branch_preview(request: Request):
        data = await parse_request(request, BranchPreview)
        target, token = write_config(data.configuration_id, "NEXUS_CONNECTOR_GITHUB_BRANCH_TOKEN")
        limiter = take_capacity(request)
        try:
            sha = await branch_head(request.app.state.client, target, token, "main")
        finally:
            limiter.release()
        expires = int(time.time()) + REVIEW_SECONDS
        return JSONResponse({"target": target, "branch": BRANCH_PREFIX + data.slug,
                             "base_sha": sha, "expires_at": expires,
                             "review_id": branch_review_id(token, target, data.slug, sha, expires)},
                            headers=NO_STORE)

    @app.post("/studio-api/connections/github/branch")
    async def create_branch(request: Request):
        data = await parse_request(request, BranchApproval)
        if not data.consent:
            raise HTTPException(422, "Explicit branch approval is required", headers=NO_STORE)
        target, token = write_config(data.configuration_id, "NEXUS_CONNECTOR_GITHUB_BRANCH_TOKEN")
        expected = branch_review_id(token, target, data.slug, data.base_sha, data.expires_at)
        if data.expires_at <= time.time() or not hmac.compare_digest(expected, data.review_id):
            raise HTTPException(409, "Branch review expired or changed", headers=NO_STORE)
        base = f"https://api.github.com/repos/{target}"
        branch = BRANCH_PREFIX + data.slug
        ref = "refs/heads/" + branch
        client = request.app.state.client
        limiter = take_capacity(request)
        try:
            try:
                result = await provider_json(client, "github", token, base + "/git/ref/heads/" + branch)
                status = "already_exists"
            except HTTPException as exc:
                if exc.status_code != 404:
                    raise
                if await branch_head(client, target, token, "main") != data.base_sha:
                    raise HTTPException(409, "Main changed; review the new commit", headers=NO_STORE) from None
                result = await provider_json(client, "github", token, base + "/git/refs",
                                             payload={"ref": ref, "sha": data.base_sha})
                status = "created"
        finally:
            limiter.release()
        # POST acknowledgement alone is insufficient. Re-fetch the ref under
        # the same operator-approved branch credential to confirm remote state.
        # Even if creation was acknowledged but read-back fails, do not claim
        # that no write happened; the caller must inspect before retrying.
        try:
            observed = await provider_json(client, "github", token,
                                           base + "/git/ref/heads/" + branch)
        except HTTPException:
            raise unconfirmed_write() from None
        if not verified_ref(observed, ref, data.base_sha):
            raise unconfirmed_write()
        return JSONResponse({
            "target": target, "branch": branch, "base_sha": data.base_sha,
            "status": status,
            "receipt": write_observation_receipt(
                "github.branch", status, "provider_ref_read_after_write"
                if status == "created" else "provider_existing_ref_read"),
        }, headers=NO_STORE)

    @app.post("/studio-api/connections/github/file-base")
    async def file_base(request: Request):
        data = await parse_request(request, FileTarget)
        target, token = write_config(data.configuration_id, "NEXUS_CONNECTOR_GITHUB_FILE_TOKEN")
        editable_path(data.path)
        branch = BRANCH_PREFIX + data.slug
        client = request.app.state.client
        limiter = take_capacity(request)
        try:
            sha = await branch_head(client, target, token, branch)
            original = await editable_file(client, target, token, sha, data.path)
        finally:
            limiter.release()
        return JSONResponse({"target": target, "branch": branch, "path": data.path,
                             "base_sha": sha, "text": original}, headers=NO_STORE)

    @app.post("/studio-api/connections/github/file-preview")
    async def file_preview(request: Request):
        data = await parse_request(request, FileDraft, MAX_FILE_REQUEST)
        target, token = write_config(data.configuration_id, "NEXUS_CONNECTOR_GITHUB_FILE_TOKEN")
        editable_path(data.path)
        raw = editable_text(data.text)
        branch = BRANCH_PREFIX + data.slug
        client = request.app.state.client
        limiter = take_capacity(request)
        try:
            if await branch_head(client, target, token, branch) != data.base_sha:
                raise HTTPException(409, "Branch changed; reload the file", headers=NO_STORE)
            original = await editable_file(client, target, token, data.base_sha, data.path)
        finally:
            limiter.release()
        diff = await anyio.to_thread.run_sync(preview_diff, original, data.text)
        expires = int(time.time()) + REVIEW_SECONDS
        return JSONResponse({"target": target, "branch": branch, "path": data.path, "base_sha": data.base_sha,
                             "diff": diff, "expires_at": expires,
                             "review_id": file_review_id(token, target, data, expires, raw)},
                            headers=NO_STORE)

    @app.post("/studio-api/connections/github/file-commit")
    async def file_commit(request: Request):
        data = await parse_request(request, FileApproval, MAX_FILE_REQUEST)
        if not data.consent:
            raise HTTPException(422, "Explicit file commit approval is required", headers=NO_STORE)
        target, token = write_config(data.configuration_id, "NEXUS_CONNECTOR_GITHUB_FILE_TOKEN")
        editable_path(data.path)
        raw = editable_text(data.text)
        expected = file_review_id(token, target, data, data.expires_at, raw)
        if data.expires_at <= time.time() or not hmac.compare_digest(expected, data.review_id):
            raise HTTPException(409, "File review expired or changed", headers=NO_STORE)
        branch = BRANCH_PREFIX + data.slug
        payload = {"query": COMMIT_QUERY, "variables": {"input": {
            "branch": {"repositoryNameWithOwner": target, "branchName": branch},
            "expectedHeadOid": data.base_sha, "message": {"headline": f"Studio: update {data.path}"[:120]},
            "fileChanges": {"additions": [{"path": data.path, "contents": base64.b64encode(raw).decode()}]},
        }}}
        limiter = take_capacity(request)
        try:
            result = await provider_json(request.app.state.client, "github", token, "https://api.github.com/graphql",
                                         payload=payload, post_status=200)
        finally:
            limiter.release()
        try:
            commit = result["data"]["createCommitOnBranch"]["commit"]["oid"]
            if result.get("errors") or not re.fullmatch(SHA, commit):
                raise ValueError()
        except (KeyError, AttributeError, TypeError, ValueError):
            raise HTTPException(409, "GitHub did not confirm a commit at the reviewed branch head", headers=NO_STORE) from None
        # A GraphQL commit identifier is an acknowledgement, not independently
        # observed persistence. Read the working branch and exact regular file
        # from the returned commit, comparing Git's blob identifier and bytes.
        # No second write or implicit retry is ever attempted.
        try:
            observed_head = await branch_head(request.app.state.client, target, token, branch)
            if observed_head != commit:
                raise ValueError("post-write-head-mismatch")
            observed_text = await editable_file(
                request.app.state.client, target, token, commit, data.path
            )
            if observed_text.encode("utf-8") != raw:
                raise ValueError("post-write-content-mismatch")
        except (HTTPException, ValueError, TypeError, AttributeError):
            raise unconfirmed_write() from None
        return JSONResponse({
            "target": target, "branch": branch, "path": data.path, "commit": commit,
            "blob_sha": git_blob_sha(raw),
            "receipt": write_observation_receipt(
                "github.file_commit", "committed", "provider_branch_and_blob_read_after_write"
            ),
        }, headers=NO_STORE)
