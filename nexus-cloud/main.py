"""Non-authoritative FastAPI transport adapter for the NEXUS Rust gateway."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request, Response, status


def _core_url() -> str | None:
    value = os.getenv("NEXUS_CORE_URL", "").strip().rstrip("/")
    return value or None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.client = httpx.AsyncClient(timeout=30.0, trust_env=False)
    yield
    await app.state.client.aclose()


app = FastAPI(
    title="NEXUS Cloud Adapter",
    version="0.1.0",
    description=(
        "A non-authoritative transport adapter for the NEXUS constitutional "
        "Rust gateway. Operational health is not epistemic correctness."
    ),
    lifespan=lifespan,
)


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
    authorization = request.headers.get("authorization", "")
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
            detail="NEXUS constitutional core is not configured",
        )

    headers = {"authorization": authorization}
    if content_type := request.headers.get("content-type"):
        headers["content-type"] = content_type
    try:
        upstream = await request.app.state.client.request(
            method=request.method,
            url=f"{core_url}/v1/{path}",
            params=request.query_params,
            headers=headers,
            content=await request.body(),
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NEXUS constitutional core is unavailable",
        ) from exc

    response_headers = {}
    if content_type := upstream.headers.get("content-type"):
        response_headers["content-type"] = content_type
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
    )
