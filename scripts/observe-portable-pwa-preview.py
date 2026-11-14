#!/usr/bin/env python3
"""Independent no-credential HTTPS witness for the frozen PWA preview deploy.

Checks public bytes against the original immutable Render deployment SHA.
Never reads private API, sends credentials, follows redirects, or mutates.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

from png_pixels import pixel_digest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "nexus_preview_build", ROOT / "scripts/prepare-portable-pwa-preview.py")
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)

ORIGIN = "https://nexus-merikation-pwa-preview.onrender.com/"
RELEASE_SHA = "4b4f32ab54fa6ce8bf4a7f0c1a428c6237307d42"
MAX_RESPONSE = 500_000
ATTEMPTS = 3


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def mime_allowed(path, value):
    value = value.split(";", 1)[0].strip().lower()
    if path.endswith(".html"):
        return value == "text/html"
    if path.endswith(".js"):
        return value in ("text/javascript", "application/javascript")
    if path.endswith(".json"):
        return value in ("application/json", "application/manifest+json")
    if path.endswith(".png"):
        return value == "image/png"
    if path.endswith(".txt"):
        return value == "text/plain"
    return False


def compare(path, status, mime, body, expected, *, redirected=False):
    output = {
        "path": path,
        "status": "FAIL_CLOSED",
        "http_status": status,
        "expected_sha256": hashlib.sha256(expected).hexdigest(),
        "observed_sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
        "exact_bytes": body == expected,
        "pixel_match": None,
    }
    if (type(status) is not int or status != 200 or redirected or
            not mime_allowed(path, mime) or not 0 < len(body) <= MAX_RESPONSE):
        return output
    if path.endswith(".png"):
        try:
            size = 192 if path.endswith("-192.png") else 512
            output["pixel_match"] = pixel_digest(body, size, size) == pixel_digest(
                expected, size, size)
        except ValueError:
            output["pixel_match"] = False
        good = output["pixel_match"] is True
    else:
        good = body == expected
    if good:
        output["status"] = "PASS"
    return output


def read_one(opener, url, max_bytes):
    request = urllib.request.Request(
        url, method="GET",
        headers={"Accept": "*/*", "Accept-Encoding": "identity",
                 "User-Agent": "NEXUS-public-static-preview-readonly/1"})
    with opener.open(request, timeout=15) as response:
        if response.headers.get("Content-Encoding", "").strip().lower() not in ("", "identity"):
            raise ValueError("unexpected-compressed-public-body")
        return (response.status, response.headers.get("Content-Type", ""),
                response.read(min(max_bytes, MAX_RESPONSE) + 1), bool(response.geturl() != url))


def witness():
    expected = BUILDER.expected(RELEASE_SHA)
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), NoRedirect())
    results = []
    for path, src in sorted(expected.items()):
        record = None
        for attempt in range(ATTEMPTS):
            try:
                status, mime, body, redirect = read_one(
                    opener, ORIGIN + path, len(src) + 4096)
                record = compare(path, status, mime, body, src, redirected=redirect)
            except (urllib.error.HTTPError, urllib.error.URLError, OSError,
                    TimeoutError, ValueError) as err:
                record = {"path": path, "status": "FAIL_CLOSED",
                          "error_type": type(err).__name__}
            if record["status"] == "PASS":
                break
            if attempt < ATTEMPTS - 1:
                time.sleep(2)
        results.append(record)

    okay = len(results) == 8 and all(x["status"] == "PASS" for x in results)
    return {
        "schema": "nexus.public-portable-pwa-preview.v1",
        "status": "PASS_PUBLIC_HTTPS_IDENTITY" if okay else "FAIL_CLOSED",
        "origin": ORIGIN,
        "deployed_source_sha": RELEASE_SHA,
        "checked_public_assets": len(results),
        "passed_assets": sum(x["status"] == "PASS" for x in results),
        "resources": results,
        "credentials_used": False,
        "production_data_touched": False,
        "android_hardware_tested": False,
        "authenticated_rust_tested": False,
        "railway_restore_proven": False,
        "release_authorized": False,
        "authority": "none",
    }


def main():
    report = witness()
    print(json.dumps(report, sort_keys=True))
    if report["status"] != "PASS_PUBLIC_HTTPS_IDENTITY":
        print("NEXUS PUBLIC PREVIEW: BLOCKED", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
