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
import studio_connections
import studio_model
import studio_vision
import studio_analysis_audit
import studio_research_evidence
import studio_research_citations
import studio_research_reasoning
import studio_research_graph
import studio_research_conflicts
import studio_research_uncertainty
import studio_research_perspectives
import studio_research_critique
import studio_research_memory
import studio_research_improvement
import studio_research_synthesis
import studio_research_export
import studio_academic
import studio_peer_review
import studio_manuscript_revision
import studio_journal_review
import studio_anonymization
import studio_document_privacy
import studio_document_extraction
import studio_document_search
import studio_document_evidence
import studio_document_generation
import studio_document_critique
import studio_document_consensus
import studio_bibliography
import studio_statistics
import studio_regression
import studio_bayesian
import studio_meta_analysis
import studio_sensitivity
import studio_regression_diagnostics
import studio_creative
import studio_analysis_export
import studio_analysis_batch
import studio_workflow
import studio_workflow_revision
from transport_bounds import read_bounded_body


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
        app.state.connections_limiter = anyio.CapacityLimiter(4)
        app.state.model_limiter = anyio.CapacityLimiter(4)
        app.state.model_budget = studio_model.create_model_request_budget()
        app.state.vision_quota = studio_vision.ProcessVisionQuota()
        app.state.gateway_limiter = anyio.CapacityLimiter(MAX_DELEGATED_REQUESTS)
        try:
            yield
        finally:
            app.state.model_budget.close()


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
studio_vision.register(app)
studio_connections.register(app)
studio_workflow.register(app)
studio_workflow_revision.register(app)
studio_analysis_batch.register(app)
studio_analysis_audit.register(app)
studio_research_evidence.register(app)
studio_research_citations.register(app)
studio_research_reasoning.register(app)
studio_research_graph.register(app)
studio_research_conflicts.register(app)
studio_research_uncertainty.register(app)
studio_research_perspectives.register(app)
studio_research_critique.register(app)
studio_research_memory.register(app)
studio_research_improvement.register(app)
studio_research_synthesis.register(app)
studio_research_export.register(app)
studio_academic.register(app)
studio_peer_review.register(app)
studio_manuscript_revision.register(app)
studio_journal_review.register(app)
studio_anonymization.register(app)
studio_document_privacy.register(app)
studio_document_extraction.register(app)
studio_document_search.register(app)
studio_document_evidence.register(app)
studio_document_generation.register(app)
studio_document_critique.register(app)
studio_document_consensus.register(app)
studio_bibliography.register(app)
studio_statistics.register(app)
studio_regression.register(app)
studio_bayesian.register(app)
studio_meta_analysis.register(app)
studio_sensitivity.register(app)
studio_regression_diagnostics.register(app)
studio_creative.register(app)
studio_analysis_export.register(app)
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
    authorization_values = request.headers.getlist("authorization")
    authorization = authorization_values[0] if len(authorization_values) == 1 else ""
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
    body = await read_bounded_body(
        request,
        max_bytes=MAX_REQUEST_BYTES,
        timeout_seconds=BODY_TIMEOUT_SECONDS,
        too_large_detail="Request body is too large",
        timeout_detail="Request body timed out",
        timeout_status=408,
    )

    headers = {"authorization": authorization, "accept-encoding": "identity"}
    if content_type := request.headers.get("content-type"):
        headers["content-type"] = content_type
    if encoding := request.headers.get("content-encoding"):
        headers["content-encoding"] = encoding
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
