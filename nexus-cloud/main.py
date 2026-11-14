"""Non-authoritative FastAPI transport adapter for the NEXUS Rust gateway."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import quote, urlsplit

import anyio

import httpx
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
import studio_model


MAX_REQUEST_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
BODY_TIMEOUT_SECONDS = 30.0
UPSTREAM_TIMEOUT_SECONDS = 30.0
MAX_DELEGATED_REQUESTS = 16


def _core_url() -> str | None:
    """Return a normalized secure core URL, or fail closed.

    The cloud adapter is a public transport edge. Its upstream configuration must
    therefore be an origin-only HTTPS URL: no credentials, path prefix, query, or
    fragment are accepted. Invalid configuration is treated the same as missing
    configuration so no request is forwarded over an ambiguous/insecure route.
    """
    value = os.getenv("NEXUS_CORE_URL", "").strip().rstrip("/")
    if not value:
        return None

    try:
        parsed = urlsplit(value)
        # Accessing .port performs additional validation (for example, malformed
        # or out-of-range port values) that urlsplit alone deliberately defers.
        _ = parsed.port
    except ValueError:
        return None

    if parsed.scheme.lower() != "https" or not parsed.hostname:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    if parsed.path or parsed.query or parsed.fragment:
        return None
    if any(character.isspace() for character in parsed.netloc):
        return None

    return value


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with httpx.AsyncClient(
        timeout=30.0, trust_env=False, follow_redirects=False,
        limits=httpx.Limits(max_connections=32, max_keepalive_connections=16),
    ) as client:
        app.state.client = client
        app.state.model_limiter = anyio.CapacityLimiter(4)
        app.state.gateway_limiter = anyio.CapacityLimiter(MAX_DELEGATED_REQUESTS)
        yield


app = FastAPI(
    title="NEXUS Cloud Adapter",
    version="0.1.0",
    description=(
        "A non-authoritative transport adapter for the NEXUS constitutional "
        "Rust gateway. Operational health is not epistemic correctness."
    ),
    lifespan=lifespan,
)


studio_model.register(app)
if studio_origin := os.getenv("NEXUS_STUDIO_ORIGIN", "").strip():
    app.add_middleware(CORSMiddleware, allow_origins=[studio_origin],
                       allow_methods=["GET", "POST"],
                       allow_headers=["authorization", "content-type"],
                       allow_credentials=False)


@app.get("/", include_in_schema=False)
async def service_metadata() -> dict[str, str]:
    return {
        "service": "nexus-cloud-adapter",
        "status": "operational",
        "authority": "none",
        "core": "configured" if _core_url() else "unconfigured",
    }


@app.get("/healthz", tags=["operations"])
async def health() -> dict[str, str]:
    return {"status": "ok", "scope": "transport-liveness-only"}


@app.api_route(
    "/v1/{path:path}", methods=["GET", "POST"], tags=["delegated NEXUS API"]
)
async def delegate_to_constitutional_gateway(path: str, request: Request) -> Response:
    """Forward an opaque request without authorizing or interpreting it."""
    authorizations = request.headers.getlist("authorization")
    # Both an edge proxy and the constitutional gateway must interpret the
    # same single credential. Never select the first/last duplicate header.
    if len(authorizations) != 1:
        raise HTTPException(
            status_code=400,
            detail="Ambiguous Authorization headers",
            headers={"Cache-Control": "no-store"},
        )
    authorization = authorizations[0]
    if not authorization.startswith("Bearer ") or not authorization[7:].strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer authentication is required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    core_url = _core_url()
    if core_url is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NEXUS constitutional core is not securely configured",
        )

    # Starlette decodes the path before handing it to this route. Re-encode
    # reserved characters so they cannot become upstream query/fragment syntax.
    if any(segment in {".", ".."} for segment in path.split("/")):
        raise HTTPException(status_code=400, detail="Invalid delegated path")

    # Admit before buffering bodies; never queue an unbounded number of callers.
    limiter = request.app.state.gateway_limiter
    try:
        limiter.acquire_nowait()
    except anyio.WouldBlock:
        raise HTTPException(
            status_code=503, detail="NEXUS gateway capacity is busy",
            headers={"Retry-After": "1", "Cache-Control": "no-store"},
        ) from None
    try:
        return await _forward_to_core(path, request, core_url, authorization)
    finally:
        # Includes malformed bodies, upstream errors and task cancellation.
        limiter.release()


async def _forward_to_core(
    path: str, request: Request, core_url: str, authorization: str
) -> Response:
    lengths = request.headers.getlist("content-length")
    content_types = request.headers.getlist("content-type")
    encodings = request.headers.getlist("content-encoding")
    # A request can be decoded or authorized differently across HTTP hops
    # when field cardinality is ambiguous. Fail before polling the body and
    # before sending any bytes to the private core.
    if len(lengths) > 1 or len(content_types) > 1 or len(encodings) > 1:
        raise HTTPException(
            status_code=400,
            detail="Ambiguous delegated request headers",
            headers={"Cache-Control": "no-store"},
        )
    declared = lengths[0] if lengths else None
    if declared is not None:
        if not declared.isascii() or not declared.isdecimal():
            raise HTTPException(status_code=400, detail="Invalid Content-Length")
        if len(declared) > 10 or int(declared) > MAX_REQUEST_BYTES:
            raise HTTPException(status_code=413, detail="Request body is too large")
    body = bytearray()
    try:
        with anyio.fail_after(BODY_TIMEOUT_SECONDS):
            async for chunk in request.stream():
                if len(body) + len(chunk) > MAX_REQUEST_BYTES:
                    raise HTTPException(status_code=413, detail="Request body is too large")
                body.extend(chunk)
    except TimeoutError as exc:
        raise HTTPException(status_code=408, detail="Request body timed out") from exc

    headers = {"authorization": authorization, "accept-encoding": "identity"}
    if content_types and content_types[0]:
        headers["content-type"] = content_types[0]
    if encodings and encodings[0]:
        headers["content-encoding"] = encodings[0]
    response_headers = {"cache-control": "no-store"}
    content = bytearray()
    try:
        with anyio.fail_after(UPSTREAM_TIMEOUT_SECONDS):
            async with request.app.state.client.stream(
                method=request.method,
                url=f"{core_url}/v1/{quote(path, safe='/')}",
                params=request.query_params.multi_items(),
                headers=headers,
                content=bytes(body),
                follow_redirects=False,
            ) as upstream:
                # Never invoke an unbounded decompressor on an opaque core response.
                # The core receives Accept-Encoding: identity; fail closed if ignored.
                if upstream.headers.get("content-encoding", "identity").lower() != "identity":
                    raise HTTPException(status_code=502, detail="Encoded core response is unsupported")
                with anyio.fail_after(BODY_TIMEOUT_SECONDS):
                    async for chunk in upstream.aiter_bytes(chunk_size=65536):
                        if len(content) + len(chunk) > MAX_RESPONSE_BYTES:
                            raise HTTPException(status_code=502, detail="Core response is too large")
                        content.extend(chunk)
                for name in ("content-type", "www-authenticate", "retry-after"):
                    if value := upstream.headers.get(name):
                        response_headers[name] = value
                upstream_status = upstream.status_code
    except (httpx.RequestError, TimeoutError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NEXUS constitutional core is unavailable",
        ) from exc

    return Response(content=bytes(content), status_code=upstream_status, headers=response_headers)
