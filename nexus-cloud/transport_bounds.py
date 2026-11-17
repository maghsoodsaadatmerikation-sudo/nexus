"""Shared fail-closed ASGI body admission for the opaque core and model edges.

This module is deliberately unaware of model and constitutional semantics. Both
public transports must enforce the same byte/framing limits before delegation.
"""
from __future__ import annotations

import anyio
from fastapi import HTTPException, Request


async def read_bounded_body(
    request: Request,
    *,
    max_bytes: int,
    timeout_seconds: float,
    too_large_detail: str,
    timeout_detail: str,
    timeout_status: int,
) -> bytes:
    """Read a single bounded body with strict HTTP Content-Length framing.

    A declared oversized body is rejected without reading it. An undeclared body
    remains streaming and is capped in bytes, not characters. Ambiguous framing
    and declared/observed length mismatch cannot be forwarded upstream.
    """
    declared_values = request.headers.getlist("content-length")
    if len(declared_values) > 1:
        raise HTTPException(status_code=400, detail="Ambiguous Content-Length")
    if declared_values and request.headers.get("transfer-encoding") is not None:
        raise HTTPException(status_code=400, detail="Ambiguous request framing")

    declared_size = None
    if declared_values:
        declared = declared_values[0]
        if not declared.isascii() or not declared.isdecimal():
            raise HTTPException(status_code=400, detail="Invalid Content-Length")
        if len(declared) > 10 or int(declared) > max_bytes:
            raise HTTPException(status_code=413, detail=too_large_detail)
        declared_size = int(declared)

    body = bytearray()
    try:
        with anyio.fail_after(timeout_seconds):
            async for chunk in request.stream():
                if len(chunk) > max_bytes - len(body):
                    raise HTTPException(status_code=413, detail=too_large_detail)
                body.extend(chunk)
    except TimeoutError as exc:
        raise HTTPException(status_code=timeout_status, detail=timeout_detail) from exc

    if declared_size is not None and len(body) != declared_size:
        raise HTTPException(status_code=400, detail="Content-Length mismatch")
    return bytes(body)
