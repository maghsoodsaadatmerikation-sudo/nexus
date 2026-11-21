#!/usr/bin/env python3
"""Read-only, fail-closed NEXUS core readiness witness for a reviewed HTTPS origin.

This does not deploy, attest, authorize, restore, or mutate anything. It is
separate from Render's ongoing /livez health check to avoid quarantine restarts.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit

MAX_RESPONSE_BYTES = 512
TIMEOUT_SECONDS = 5


class ReadinessFailure(ValueError):
    pass


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ReadinessFailure(reason)


def origin_from_config(value: str) -> str:
    require(isinstance(value, str) and bool(value) and value == value.strip(),
            "missing or ambiguous NEXUS_BASE_URL")
    require(not any(c.isspace() for c in value) and "\\" not in value,
            "invalid origin characters")
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError as error:
        raise ReadinessFailure("invalid origin URL") from error
    require(parts.scheme == "https" and bool(parts.hostname),
            "origin must use HTTPS")
    require(parts.username is None and parts.password is None,
            "origin must not contain credentials")
    require(parts.path in ("", "/") and not parts.query and not parts.fragment,
            "origin must not contain path, query or fragment")
    require(parts.hostname not in {"localhost", "127.0.0.1", "::1"},
            "production readiness requires public HTTPS origin")
    require(port is None or 1 <= port <= 65535, "invalid port")
    require("@" not in parts.netloc and "%" not in parts.netloc,
            "ambiguous origin authority")
    return "https://" + parts.netloc.rstrip("/")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def check_readiness(origin: str, opener=None) -> None:
    url = origin + "/readyz"
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "Accept-Encoding": "identity"},
        method="GET",
    )
    if opener is None:
        # No ambient proxy credentials or automatic redirects, ever.
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect()
        )
    with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
        require(response.geturl() == url, "readiness redirect is forbidden")
        require(response.status == 200, "readiness did not return HTTP 200")
        headers = response.headers
        content_type = headers.get("content-type", "").lower().split(";", 1)[0].strip()
        require(content_type == "application/json", "unexpected readiness content type")
        require(headers.get("content-encoding", "identity").lower() == "identity",
                "encoded readiness response is not accepted")
        declared = headers.get("content-length")
        if declared is not None:
            require(declared.isascii() and declared.isdecimal()
                    and int(declared) <= MAX_RESPONSE_BYTES,
                    "invalid readiness body length")
        require("no-store" in headers.get("cache-control", "").lower(),
                "readiness response must not be cached")
        payload = response.read(MAX_RESPONSE_BYTES + 1)
        require(len(payload) <= MAX_RESPONSE_BYTES, "oversized readiness response")
    try:
        body = json.loads(payload.decode("utf-8"))
    except (ValueError, UnicodeError) as error:
        raise ReadinessFailure("invalid readiness JSON") from error
    require(body == {"status": "ready"}, "gateway not ready")


def main() -> None:
    require(len(sys.argv) == 1, "no positional arguments are supported")
    origin = origin_from_config(os.getenv("NEXUS_BASE_URL", ""))
    try:
        check_readiness(origin)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise ReadinessFailure("readiness observation unavailable") from error
    print("NEXUS LIVE READINESS: PASS")
    print("Status: HTTP 200 /readyz / status=ready")
    print("Source: LIVE HTTPS OBSERVATION ONLY")
    print("Stage D Recovery Evidence: NOT ESTABLISHED")
    print("Deployment Authorization: NONE")


if __name__ == "__main__":
    try:
        main()
    except ReadinessFailure as error:
        print(f"NEXUS LIVE READINESS: BLOCKED ({error})", file=sys.stderr)
        raise SystemExit(1)
