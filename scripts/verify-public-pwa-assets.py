#!/usr/bin/env python3
"""Independently observe exact public Pilot 12 installable assets; no credentials.

GET only five exact static public paths, no redirect, no secrets or workspace.
This does NOT assert original Railway volume recoverability or real Android usage.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import time
import urllib.error
import urllib.request

ORIGIN = "https://nexus-offline-pilot.onrender.com"
ASSETS = {
    "/": ("web/offline-pilot.html", "text/html"),
    "/manifest.webmanifest": ("public/manifest.webmanifest", "manifest"),
    "/service-worker.js": ("public/service-worker.js", "javascript"),
    "/icons/nexus-192.png": ("public/icons/nexus-192.png", "image/png"),
    "/icons/nexus-512.png": ("public/icons/nexus-512.png", "image/png"),
}
MAX_BYTES = 300_000


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def allowed_mime(kind: str, value: str) -> bool:
    mime = value.split(";", 1)[0].strip().lower()
    if kind == "manifest":
        return mime in ("application/manifest+json", "application/json")
    if kind == "javascript":
        return mime in ("text/javascript", "application/javascript")
    return mime == kind


def compare(status: int, mime: str, body: bytes, expected: bytes, kind: str) -> dict:
    ok = (status == 200 and 0 < len(body) <= MAX_BYTES
          and body == expected and allowed_mime(kind, mime))
    return {
        "ok": ok,
        "http_status": status,
        "mime_type": mime.split(";", 1)[0].strip().lower()[:72],
        "sha256": hashlib.sha256(body).hexdigest(),
        "expected_sha256": hashlib.sha256(expected).hexdigest(),
        "bytes": len(body),
        "exact_byte_match": body == expected,
    }


def source_sanity() -> None:
    html = Path("web/offline-pilot.html").read_bytes()
    sw = Path("public/service-worker.js").read_text("utf-8")
    manifest = json.loads(Path("public/manifest.webmanifest").read_text("utf-8"))
    assert b"connect-src 'none'" in html
    assert b"worker-src 'self'" in html
    assert b"manifest-src 'self'" in html
    assert hashlib.sha256(html).hexdigest() in sw
    assert "const EXPECTED_SHA256='" + hashlib.sha256(html).hexdigest() + "'" in sw
    assert "navigator.serviceWorker.register('/service-worker.js'" in html.decode()
    assert manifest["scope"] == manifest["start_url"] == "/"
    assert manifest["display"] == "standalone"
    assert {x["sizes"] for x in manifest["icons"]} == {"192x192", "512x512"}
    for size in (192, 512):
        data = Path(f"public/icons/nexus-{size}.png").read_bytes()
        assert data.startswith(b"\x89PNG\r\n\x1a\n")
        assert struct.unpack(">II", data[16:24]) == (size, size)


def self_test() -> None:
    expected = b"app-shell"
    assert compare(200, "text/html; charset=utf-8", expected, expected, "text/html")["ok"]
    assert not compare(302, "text/html", expected, expected, "text/html")["ok"]
    assert not compare(200, "application/json", expected, expected, "text/html")["ok"]
    assert not compare(200, "text/html", expected + b"x", expected, "text/html")["ok"]
    assert not compare(200, "text/html", b"", expected, "text/html")["ok"]
    assert allowed_mime("manifest", "application/manifest+json; charset=utf-8")
    assert allowed_mime("javascript", "text/javascript; charset=utf-8")
    assert not allowed_mime("manifest", "text/plain")
    assert not allowed_mime("javascript", "text/html")
    source_sanity()
    print(json.dumps({"status": "PASS", "negative_fixtures": 6,
                      "positive_fixtures": 3, "production_mutation": False}))


def public_observation(attempts: int) -> dict:
    assert 1 <= attempts <= 6
    source_sanity()
    opener = urllib.request.build_opener(NoRedirect)
    result = {}
    for path, (file, kind) in ASSETS.items():
        expected = Path(file).read_bytes()
        assert 0 < len(expected) <= MAX_BYTES
        observation = None
        for attempt in range(attempts):
            request = urllib.request.Request(
                ORIGIN + path,
                method="GET",
                headers={
                    "Accept": "text/html" if path == "/" else "*/*",
                    "User-Agent": "NEXUS-pilot12-static-readonly-observer/1",
                })
            try:
                with opener.open(request, timeout=16) as response:
                    data = response.read(MAX_BYTES + 1)
                    observation = compare(
                        response.status,
                        response.headers.get("Content-Type", ""),
                        data, expected, kind)
            except urllib.error.HTTPError as exc:
                observation = compare(exc.code, "", b"", expected, kind)
            except (urllib.error.URLError, TimeoutError) as exc:
                observation = {
                    "ok": False,
                    "error_type": type(exc).__name__,
                    "expected_sha256": hashlib.sha256(expected).hexdigest(),
                }
            if observation["ok"]:
                break
            if attempt + 1 < attempts:
                time.sleep(5)
        assert observation is not None
        # Path is a fixed constant, and output only contains public hashes.
        result[path] = observation
    success = all(x["ok"] for x in result.values())
    return {
        "schema": "nexus.pilot-12.public-assets-witness.v1",
        "status": "PASS" if success else "FAIL_CLOSED",
        "origin": ORIGIN,
        "resources": result,
        "verified_resources": sum(x["ok"] for x in result.values()),
        "user_data_seen": False,
        "server_credentials_used": False,
        "authenticated_rust_tested": False,
        "original_volume_restore_proven": False,
        "production_mutation": False,
        "authority": "none",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--attempts", type=int, default=3)
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    report = public_observation(args.attempts)
    print(json.dumps(report, sort_keys=True))
    if report["status"] != "PASS":
        raise SystemExit("BLOCKED: public static installable asset identity mismatch")


if __name__ == "__main__":
    main()
