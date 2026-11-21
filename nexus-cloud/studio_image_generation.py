"""Operator-disabled image generation bridge; one reviewed request, one inert image.

This adapter never edits images, executes tools, writes files, or retains prompts.
The provider may have its own data retention policy; the operator must review it.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import threading
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

import anyio
import httpx
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

import studio_vision
from transport_bounds import read_bounded_body

MAX_REQUEST = 10_000
MAX_RESPONSE = 9_000_000
MAX_IMAGE = 6_000_000
POLICY_VERSION = 'nexus-image-generation-v1'


@dataclass(frozen=True)
class ImageConfig:
    url: str
    model: str
    token: str
    api_key: str
    host: str
    wire_format: str


def config() -> ImageConfig | None:
    """Never accept client-supplied URLs or implicit provider credentials."""
    if os.getenv('NEXUS_IMAGE_ENABLED') != '1':
        return None
    url = os.getenv('NEXUS_IMAGE_URL', '')
    model = os.getenv('NEXUS_IMAGE_MODEL', '')
    token = os.getenv('NEXUS_STUDIO_TOKEN', '')
    key = os.getenv('NEXUS_IMAGE_API_KEY', '')
    wire_format = os.getenv('NEXUS_IMAGE_WIRE_FORMAT', 'gpt')
    if not (len(token) >= 32 and token.strip() == token and
            len(key) >= 8 and key.strip() == key and
            re.fullmatch(r'[A-Za-z0-9._/-]{1,120}', model) and
            wire_format in ('gpt', 'legacy')):
        return None
    try:
        parsed = urlsplit(url)
        _ = parsed.port
    except ValueError:
        return None
    if (parsed.scheme != 'https' or not parsed.hostname or
            parsed.username is not None or parsed.password is not None or
            not parsed.path.endswith('/images/generations') or
            parsed.query or parsed.fragment or
            any(ch.isspace() for ch in url)):
        return None
    return ImageConfig(url, model, token, key, parsed.hostname, wire_format)


def configuration_id(c: ImageConfig) -> str:
    # HMAC binds the operator's private configuration, including key rotation,
    # without exposing a raw hash of the provider credential to the browser.
    material = '\x00'.join((POLICY_VERSION, c.url, c.model, c.api_key, c.wire_format)).encode()
    return hmac.new(c.token.encode(), material, hashlib.sha256).hexdigest()


def request_cap() -> int | None:
    raw = os.getenv('NEXUS_IMAGE_MAX_REQUESTS_PER_PROCESS', '')
    if not re.fullmatch(r'[1-9][0-9]{0,3}', raw):
        return None
    value = int(raw)
    return value if value <= 1000 else None


class ProcessQuota:
    """Atomic guard for provider attempts, not a global or durable billing cap."""
    def __init__(self):
        self._lock = threading.Lock()
        self._used = 0

    def remaining(self, limit: int) -> int:
        with self._lock:
            return max(0, limit - self._used)

    def reserve(self, limit: int) -> bool:
        with self._lock:
            if self._used >= limit:
                return False
            self._used += 1
            return True


class GenerateRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid')
    consent: Literal[True]
    configuration_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    prompt: str = Field(min_length=1, max_length=2000)
    size: Literal['1024x1024', '1024x1536', '1536x1024'] = '1024x1024'

    @field_validator('consent', mode='before')
    @classmethod
    def consent_must_be_boolean(cls, value):
        if value is not True:
            raise ValueError('Boolean true required')
        return value

    @field_validator('prompt')
    @classmethod
    def prompt_cannot_be_blank(cls, value):
        if not value.strip():
            raise ValueError('Nonblank prompt required')
        return value


def decode_image(payload: bytes) -> tuple[str, str]:
    """Only canonical bounded PNG/JPEG bytes; provider URLs are not followed."""
    try:
        result = json.loads(payload)
        items = result['data']
        if not isinstance(items, list) or len(items) != 1:
            raise ValueError('count')
        encoded = items[0]['b64_json']
        if not isinstance(encoded, str) or not encoded or len(encoded) > 8_000_000:
            raise ValueError('image')
        raw = base64.b64decode(encoded, validate=True)
        if (len(raw) > MAX_IMAGE or
                base64.b64encode(raw).decode('ascii') != encoded):
            raise ValueError('size or canonical encoding')
        if studio_vision.valid_png(raw):
            kind = 'image/png'
        elif studio_vision.valid_jpeg(raw):
            kind = 'image/jpeg'
        else:
            raise ValueError('invalid image')
        return encoded, kind
    except (KeyError, TypeError, IndexError, ValueError, binascii.Error) as exc:
        raise HTTPException(502, 'Image provider returned invalid image data') from None


def register(app):
    @app.get('/studio-api/image-generation-status')
    async def image_generation_status(request: Request):
        c = config()
        limit = request_cap()
        remaining = request.app.state.image_quota.remaining(limit) if limit is not None else 0
        available = c is not None and limit is not None and remaining > 0
        reason = ('disabled' if c is None else
                  'limit-unconfigured' if limit is None else
                  'limit-reached' if remaining == 0 else 'configured')
        return JSONResponse({
            'configured': available,
            'reason': reason,
            'configuration_id': configuration_id(c) if available else None,
            'model': c.model if available else None,
            'provider_host': c.host if available else None,
            'authority': 'none'
        }, headers={'Cache-Control': 'no-store'})

    @app.post('/studio-api/generate-image')
    async def generate_image(request: Request):
        c = config()
        if c is None:
            raise HTTPException(503, 'Image generation is not enabled')
        limit = request_cap()
        if limit is None:
            raise HTTPException(503, 'Image generation process quota required')
        authorizations = request.headers.getlist('authorization')
        auth = authorizations[0] if len(authorizations) == 1 else ''
        if not hmac.compare_digest(auth.encode(), ('Bearer ' + c.token).encode()):
            raise HTTPException(401, 'Studio authentication required',
                                headers={'WWW-Authenticate': 'Bearer'})
        content_types = request.headers.getlist('content-type')
        if len(content_types) != 1 or content_types[0].split(';', 1)[0].strip().lower() != 'application/json':
            raise HTTPException(415, 'JSON required')
        try:
            request.app.state.image_limiter.acquire_nowait()
        except anyio.WouldBlock:
            raise HTTPException(429, 'Image generation is busy', headers={'Retry-After': '5'}) from None
        try:
            body = await read_bounded_body(
                request, max_bytes=MAX_REQUEST, timeout_seconds=30,
                too_large_detail='Image request too large',
                timeout_detail='Image request timed out', timeout_status=504)
            try:
                data = GenerateRequest.model_validate_json(body)
            except ValidationError:
                raise HTTPException(422, 'Invalid reviewed image generation request') from None
            if data.configuration_id != configuration_id(c):
                raise HTTPException(409, 'Image provider configuration changed; review again')
            if not request.app.state.image_quota.reserve(limit):
                raise HTTPException(429, 'Image provider attempt quota reached')
            content = bytearray()
            payload = {'model': c.model, 'prompt': data.prompt, 'size': data.size, 'n': 1}
            if c.wire_format == 'gpt':
                payload['output_format'] = 'png'  # Modern GPT Image: base64 by default.
            else:
                payload['response_format'] = 'b64_json'  # Legacy compatible providers.
            try:
                with anyio.fail_after(60):
                    async with request.app.state.client.stream(
                        'POST', c.url,
                        json=payload,
                        headers={'authorization': 'Bearer ' + c.api_key,
                                 'accept-encoding': 'identity'},
                        follow_redirects=False,
                    ) as response:
                        if (response.status_code != 200 or
                                response.headers.get('content-encoding', 'identity').lower() != 'identity'):
                            raise HTTPException(502, 'Image provider request failed')
                        declared = response.headers.get('content-length')
                        if declared is not None and (not re.fullmatch(r'[0-9]{1,10}', declared)
                                                     or int(declared) > MAX_RESPONSE):
                            raise HTTPException(502, 'Invalid or oversized image provider response')
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            if len(chunk) > MAX_RESPONSE - len(content):
                                raise HTTPException(502, 'Image provider response too large')
                            content.extend(chunk)
            except TimeoutError:
                raise HTTPException(504, 'Image provider timed out') from None
            except (httpx.HTTPError, ValueError):
                raise HTTPException(502, 'Image provider request failed') from None
            encoded, kind = decode_image(content)
            return JSONResponse({
                'image_base64': encoded, 'mime_type': kind,
                'model': c.model, 'authority': 'none',
                'storage': 'not-retained-by-nexus'
            }, headers={'Cache-Control': 'no-store'})
        finally:
            request.app.state.image_limiter.release()
