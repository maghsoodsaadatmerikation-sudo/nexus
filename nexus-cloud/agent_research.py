"""Consent-scoped, read-only developer metadata lookup for a local NEXUS operator.

This is not general web search, browser automation or a networked code sandbox.
Targets are fixed public HTTPS APIs, never arbitrary operator/model-provided URLs.
Content from any third party remains untrusted and is not sent to a model.
"""
from __future__ import annotations

import hashlib
import json
import re
import ssl
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener

MAX_REMOTE_BYTES = 1_048_576
MAX_NAME_LENGTH = 128
_PACKAGE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}\Z")
_GITHUB_COMPONENT = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}\Z")


class ResearchDenied(ValueError):
    """A live metadata fetch violates input, network or response constraints."""


class _DenyRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _open_public_https(request: Request, timeout: float):
    # No ambient HTTP(S)_PROXY or machine credentials are inherited.
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()), _DenyRedirects())
    return opener.open(request, timeout=timeout)


def endpoint(provider: str, name: str) -> str:
    """Return a fixed-authority public URL or reject; no arbitrary URL input."""
    if not isinstance(name, str) or len(name) > MAX_NAME_LENGTH or not isinstance(provider, str):
        raise ResearchDenied("invalid-research-target")
    if provider in ("pypi", "crates"):
        if not _PACKAGE.fullmatch(name) or name in (".", ".."):
            raise ResearchDenied("invalid-package-name")
        encoded = quote(name, safe="")
        if provider == "pypi":
            return f"https://pypi.org/pypi/{encoded}/json"
        return f"https://crates.io/api/v1/crates/{encoded}"
    if provider == "github-release":
        parts = name.split("/")
        if len(parts) != 2 or not all(_GITHUB_COMPONENT.fullmatch(p) and p not in (".", "..") for p in parts):
            raise ResearchDenied("invalid-github-repository")
        return f"https://api.github.com/repos/{quote(parts[0], safe='')}/{quote(parts[1], safe='')}/releases/latest"
    raise ResearchDenied("unsupported-research-provider")


def _required_string(value, *, max_length: int = 180) -> str:
    if not isinstance(value, str) or not value or len(value) > max_length:
        raise ResearchDenied("invalid-source-metadata")
    return value


def fetch_metadata(provider: str, name: str, *, open_request=None) -> dict[str, object]:
    """Fetch explicitly selected public metadata without redirects or proxies.

    The optional opener is test-only dependency injection; callers may not supply
    raw URLs, credentials, HTTP methods, cookies, or user-defined headers.
    """
    url = endpoint(provider, name)
    request = Request(url, method="GET", headers={
        "User-Agent": "NEXUS-local-research/1.0 (+read-only; no-auth)",
        "Accept": "application/json",
        "Accept-Encoding": "identity",
    })
    opener = open_request or _open_public_https
    try:
        with opener(request, timeout=8.0) as response:
            if response.geturl() != url or response.status != 200:
                raise ResearchDenied("research-redirect-or-status")
            content_type = response.headers.get("Content-Type", "").lower().split(";", 1)[0].strip()
            if content_type != "application/json" and not content_type.endswith("+json"):
                raise ResearchDenied("research-not-json")
            declared = response.headers.get("Content-Length", "")
            if declared:
                if not declared.isdecimal() or int(declared) > MAX_REMOTE_BYTES:
                    raise ResearchDenied("research-size")
            chunks, total = [], 0
            while True:
                piece = response.read(min(65_536, MAX_REMOTE_BYTES + 1 - total))
                if not piece:
                    break
                total += len(piece)
                if total > MAX_REMOTE_BYTES:
                    raise ResearchDenied("research-size")
                chunks.append(piece)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        # Do not leak URLs, response bodies or environment credentials to receipts.
        raise ResearchDenied("research-unavailable") from exc
    raw = b"".join(chunks)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ResearchDenied("research-invalid-json") from exc
    if not isinstance(payload, dict):
        raise ResearchDenied("research-invalid-response")
    if provider == "pypi":
        info = payload.get("info")
        if not isinstance(info, dict):
            raise ResearchDenied("research-invalid-response")
        title = _required_string(info.get("name"))
        version = _required_string(info.get("version"))
    elif provider == "crates":
        crate = payload.get("crate")
        if not isinstance(crate, dict):
            raise ResearchDenied("research-invalid-response")
        title = _required_string(crate.get("id"))
        version = _required_string(crate.get("max_version"))
    else:
        title = _required_string(payload.get("name") or payload.get("tag_name"))
        version = _required_string(payload.get("tag_name"))
    return {
        "provider": provider,
        "query": name,
        "title": title,
        "version": version,
        "source_url": url,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "provenance": "external-provider-metadata-unverified",
    }
