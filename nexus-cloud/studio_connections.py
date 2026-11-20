"""Operator-configured, read-only connections for the Studio workspace."""

import base64
import binascii
import hashlib
import hmac
import json
import os
import re
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


async def read_provider(client, data, provider, target, token):
    url, params = provider_request(data, target)
    headers = {"accept": "application/json", "accept-encoding": "identity"}
    if provider == "github":
        headers.update({"accept": "application/vnd.github+json", "x-github-api-version": "2022-11-28"})
    if token:
        headers["authorization"] = "Bearer " + token
    body = bytearray()
    # GitHub includes each full PR description even though Studio only needs metadata.
    limit = MAX_PULL_RESPONSE if data.operation == "github.pulls" else MAX_RESPONSE
    try:
        with anyio.fail_after(12):
            async with client.stream("GET", url, params=params, headers=headers,
                                     follow_redirects=False) as reply:
                if reply.status_code in {401, 403}:
                    raise HTTPException(502, "Provider access was denied")
                if reply.status_code == 404:
                    raise HTTPException(404, "Provider resource is unavailable")
                if reply.status_code != 200 or reply.headers.get("content-encoding", "identity").lower() != "identity":
                    raise HTTPException(502, "Provider did not return a supported response")
                async for chunk in reply.aiter_bytes(chunk_size=8192):
                    if len(body) + len(chunk) > limit:
                        raise HTTPException(502, "Provider response exceeded the limit")
                    body.extend(chunk)
    except (httpx.RequestError, TimeoutError):
        raise HTTPException(504, "Provider did not respond in time") from None
    try:
        return project_result(data.operation, json.loads(body), data.path)
    except (ValueError, KeyError, AttributeError, TypeError, RecursionError, binascii.Error):
        raise HTTPException(502, "Provider result is not supported text or metadata") from None


def register(app):
    @app.get("/studio-api/connections")
    async def catalog(request: Request):
        operator_auth(request)
        targets = configured()
        return JSONResponse({"connections": [
            {"provider": provider, "target": target, "configuration_id": target_id(provider, target)}
            for provider, (target, _) in targets.items()
        ]}, headers=NO_STORE)

    @app.post("/studio-api/connections/read")
    async def read(request: Request):
        operator_auth(request)
        media = request.headers.getlist("content-type")
        if len(media) != 1 or media[0].split(";", 1)[0].strip().lower() != "application/json":
            raise HTTPException(415, "JSON required", headers=NO_STORE)
        raw = await read_bounded_body(request, max_bytes=4096, timeout_seconds=6,
                                      too_large_detail="Connection request too large",
                                      timeout_detail="Connection request timed out", timeout_status=408)
        try:
            data = ReadRequest.model_validate_json(raw)
        except ValidationError:
            raise HTTPException(422, "Invalid connection request", headers=NO_STORE) from None
        if not data.consent or (data.operation != "github.file" and (data.path or data.revision)):
            raise HTTPException(422, "Review the exact connection request", headers=NO_STORE)
        provider = OPERATIONS[data.operation]
        entry = configured().get(provider)
        if entry is None or data.configuration_id != target_id(provider, entry[0]):
            raise HTTPException(409, "Connection changed or is disabled", headers=NO_STORE)
        limiter = request.app.state.connections_limiter
        try:
            limiter.acquire_nowait()
        except anyio.WouldBlock:
            raise HTTPException(429, "Connections are busy", headers=NO_STORE) from None
        try:
            result = await read_provider(request.app.state.client, data, provider, *entry)
        finally:
            limiter.release()
        return JSONResponse({"provider": provider, "target": entry[0], "operation": data.operation,
                             "provenance": "external-untrusted", "result": result}, headers=NO_STORE)
