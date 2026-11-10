#!/usr/bin/env python3
"""Independently check Render static pilot's *public, unauthenticated* bytes.

No auth headers, POST, mutation, operator data, Railway endpoint or secrets.
Only explicit HTTPS GET of an allowlisted static pilot URL.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

DEFAULT_URL = "https://nexus-offline-pilot.onrender.com/"
ALLOWED_HOST = "nexus-offline-pilot.onrender.com"
MAX_HTML_BYTES = 300_000


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def inspect_response(status, html, expected):
    """Small pure function so negative cases can be checked without network."""
    observed_hash = hashlib.sha256(html).hexdigest()
    good = (status == 200
            and 0 < len(html) <= MAX_HTML_BYTES
            and html == expected
            and b"connect-src 'none'" in html
            and b"nexus.offline-pilot.v1" in html)
    return {
        "status": "PASS_STATIC_HTTPS_IDENTITY" if good else "FAIL_STATIC_HTTPS_IDENTITY",
        "http_status": status,
        "observed_sha256": observed_hash,
        "expected_sha256": hashlib.sha256(expected).hexdigest(),
        "observed_bytes": len(html),
        "matched_exact_html": html == expected,
        "hosted_file_only": True,
        "authenticated_live_user": False,
        "external_volume_restore_verified": False,
        "production_mutation": False,
        "authority": "none",
    }


def test():
    data = b"<!doctype html><title>NEXUS</title>nexus.offline-pilot.v1 connect-src 'none'"
    assert inspect_response(200, data, data)["status"] == "PASS_STATIC_HTTPS_IDENTITY"
    assert inspect_response(404, data, data)["status"].startswith("FAIL")
    assert inspect_response(200, data + b"x", data)["status"].startswith("FAIL")
    assert inspect_response(200, b"", data)["status"].startswith("FAIL")
    assert inspect_response(200, b"x", b"x")["status"].startswith("FAIL")
    print(json.dumps({"scope": "pure-local-fixtures", "checks": 5, "status": "PASS"}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--expected", default="web/offline-pilot.html")
    parser.add_argument("--attempts", type=int, default=5)
    args = parser.parse_args()
    if args.self_test:
        test()
        return
    # This tool is intentionally restricted to the fixed public pilot hostname.
    if args.url != DEFAULT_URL or not (1 <= args.attempts <= 8):
        raise SystemExit("FAIL: the static observer only accepts the exact public pilot URL")
    expected = Path(args.expected).read_bytes()
    if not (0 < len(expected) <= MAX_HTML_BYTES):
        raise SystemExit("FAIL: expected source size outside bounds")
    opener = urllib.request.build_opener(NoRedirect)
    report = None
    for attempt in range(args.attempts):
        request = urllib.request.Request(
            DEFAULT_URL,
            headers={"Accept": "text/html", "User-Agent": "NEXUS-static-readonly-observer/1"},
            method="GET"
        )
        try:
            with opener.open(request, timeout=18) as response:
                body = response.read(MAX_HTML_BYTES + 1)
                report = inspect_response(response.status, body, expected)
                report["content_type"] = response.headers.get("Content-Type", "")
                if not report["content_type"].lower().startswith("text/html"):
                    report["status"] = "FAIL_STATIC_HTTPS_IDENTITY"
        except urllib.error.HTTPError as exc:
            report = inspect_response(exc.code, b"", expected)
        except (urllib.error.URLError, TimeoutError) as exc:
            report = {
                "status": "FAIL_STATIC_HTTPS_IDENTITY", "error_type": type(exc).__name__,
                "http_status": None,
                "production_mutation": False, "authenticated_live_user": False,
                "external_volume_restore_verified": False, "authority": "none",
            }
        if report["status"] == "PASS_STATIC_HTTPS_IDENTITY":
            break
        if attempt + 1 < args.attempts:
            time.sleep(8)
    assert report is not None
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["status"] != "PASS_STATIC_HTTPS_IDENTITY":
        sys.exit(1)


if __name__ == "__main__":
    main()
