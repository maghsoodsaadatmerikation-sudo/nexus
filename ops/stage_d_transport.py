#!/usr/bin/env python3
"""Bounded same-origin HTTPS transport for the historical Stage D operator.

No redirects, no environment proxies, no credentials in process argv. The
operator must not infer a production recovery or release from this transport.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

MAX_RESPONSE = 2 * 1024 * 1024
MAX_REQUEST = 2 * 1024 * 1024
TIMEOUT_SECONDS = 10


class TransportBlocked(ValueError):
    """Sanitized refusal; never exposes provider URLs or bearer material."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def origin(base):
    if (type(base) is not str or not 0 < len(base) <= 2048
            or any(ch.isspace() or ord(ch) < 32 for ch in base)):
        raise TransportBlocked("invalid-origin")
    try:
        url = urllib.parse.urlsplit(base)
        valid = (url.scheme == "https" and bool(url.hostname)
                 and url.port in (None, 443)
                 and url.username is None and url.password is None
                 and url.path in ("", "/") and not url.query and not url.fragment)
    except ValueError:
        valid = False
    if not valid:
        raise TransportBlocked("invalid-origin")
    return "https://" + url.netloc


def route_allowed(method, path):
    if type(path) is not str or not path.startswith("/") or "?" in path or "#" in path:
        return False
    if method == "GET":
        return path == "/" or (path != "/v1/workspaces/import" and
            bool(re.fullmatch(r"/v1/workspaces/[A-Za-z0-9_-]{1,100}", path)))
    if method == "POST":
        return path in ("/v1/workspaces", "/v1/workspaces/import")
    return False


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise TransportBlocked("duplicate-json-field")
        result[key] = value
    return result


def disallow_constant(_):
    raise TransportBlocked("invalid-json-constant")


def bounded_read(response):
    headers = response.headers
    try:
        lengths = headers.get_all("Content-Length", []) if hasattr(headers, "get_all") else []
        if len(lengths) > 1 or (lengths and
            (not lengths[0].isdigit() or int(lengths[0]) > MAX_RESPONSE)):
            raise TransportBlocked("invalid-response-length")
        body = response.read(MAX_RESPONSE + 1)
    except (ValueError, TypeError, OverflowError):
        raise TransportBlocked("invalid-response-length") from None
    if len(body) > MAX_RESPONSE:
        raise TransportBlocked("response-too-large")
    if lengths and int(lengths[0]) != len(body):
        raise TransportBlocked("incomplete-response")
    return body


def checked_response(response, path):
    status = response.status if hasattr(response, "status") else response.code
    if type(status) is not int or status < 200 or status > 599 or 300 <= status < 400:
        raise TransportBlocked("redirect-or-invalid-status")
    headers = response.headers
    if path != "/":
        cache = headers.get("Cache-Control", "")
        if "no-store" not in {part.strip().lower() for part in cache.split(",")}:
            raise TransportBlocked("cacheable-private-response")
        mime = headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if mime != "application/json":
            raise TransportBlocked("invalid-private-media-type")
    raw = bounded_read(response)
    if path != "/":
        try:
            data = json.loads(raw, object_pairs_hook=unique_object,
                              parse_constant=disallow_constant)
        except (UnicodeError, ValueError, TypeError):
            raise TransportBlocked("invalid-private-json") from None
        if type(data) is not dict:
            raise TransportBlocked("invalid-private-json-shape")
    return status, raw


def request(base, path, method="GET", body=None, token=None, *, opener=None):
    base = origin(base)
    if not route_allowed(method, path):
        raise TransportBlocked("unapproved-operator-route")
    if (token is not None and (type(token) is not str or
            not 0 < len(token) <= 4096 or
            any(ch.isspace() or ord(ch) < 32 for ch in token))):
        raise TransportBlocked("invalid-token")
    if method == "POST" and token is None:
        raise TransportBlocked("unauthenticated-write")
    if body is not None and method != "POST":
        raise TransportBlocked("body-on-read")
    try:
        data = None if body is None else json.dumps(
            body, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError):
        raise TransportBlocked("invalid-request-json") from None
    if data is not None and len(data) > MAX_REQUEST:
        raise TransportBlocked("request-too-large")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    transport = opener if opener is not None else urllib.request.build_opener(
        urllib.request.ProxyHandler({}), NoRedirect())
    try:
        try:
            response = transport.open(req, timeout=TIMEOUT_SECONDS)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return checked_response(response, path)
    except (urllib.error.URLError, OSError, TimeoutError, ConnectionError):
        raise TransportBlocked("transport-failure") from None
