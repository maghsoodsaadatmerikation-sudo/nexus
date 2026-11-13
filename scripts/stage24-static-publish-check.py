#!/usr/bin/env python3
"""Stage 24: validate a static-only GitHub Pages snapshot and public HTTPS bytes.

No provider token, authentication, mutation, secret, external account or
original Railway data is needed for these read-only checks.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PAGES_URL = "https://maghsoodsaadatmerikation-sudo.github.io/nexus/"
PUBLIC_FILES = (
    "", "index.html", "manifest.json", "service-worker.js",
    "icons/nexus-192.png", "icons/nexus-512.png",
    "nexus-stage23-integrity.json",
)
SOURCE_PINS = {
    "scripts/build-work-mode-portable.py": "3c310ef6547955a79a4ad45eef976cfa0ee29bdd",
    "scripts/build-mobile-work-pwa.py": "8815f3cd2eab596a2b2d80493ab0d81a8b843a76",
    "scripts/test-mobile-work-pwa.py": "b958f4b9797727767d1936b55c551c782ae13240",
    "scripts/test-mobile-work-pwa-browser.mjs": "78b1514b33d46be1b7a5d17c1fa7d8489ba94018",
    "web/work-mode.html": "90602f97170915633f267bd26a067507b6e193c3",
    "web/work-mode-core.js": "0f0fc4a155fd1996b07ada293e3330c29f8ec0c7",
    "public/icons/nexus-192.png": "8fb8d9dbc8dd72431b5674eff5597d233cd9f4d9",
    "public/icons/nexus-512.png": "eea09d737a9ea62ee60c53598b7eff1c8ad3998d",
}
ALLOWED_MIME = {
    "": {"text/html"},
    "index.html": {"text/html"},
    "manifest.json": {"application/json", "application/manifest+json"},
    "service-worker.js": {"application/javascript", "text/javascript"},
    "icons/nexus-192.png": {"image/png"},
    "icons/nexus-512.png": {"image/png"},
    "nexus-stage23-integrity.json": {"application/json"},
}


class Refused(Exception):
    pass


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise Refused(reason)


def source_pins() -> dict[str, str]:
    actual = {}
    for name in SOURCE_PINS:
        x = subprocess.run(["git", "rev-parse", "HEAD:" + name],
                           cwd=ROOT, text=True, capture_output=True,
                           timeout=8, check=True)
        actual[name] = x.stdout.strip()
    require(actual == SOURCE_PINS, "reviewed_source_blob_changed")
    return actual


def stage23_builder():
    path = ROOT / "scripts" / "build-mobile-work-pwa.py"
    spec = importlib.util.spec_from_file_location("nexus_stage23_builder_v24", path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def validate_site(site: Path, expected: dict[str, bytes] | None = None) -> dict:
    site = site.resolve(strict=True)
    require(site.is_dir(), "not_directory")
    if expected is None:
        expected = stage23_builder().produce()
    require("index.html" in expected and ".nojekyll" in expected,
            "invalid_reviewed_site")
    actual = set()
    for item in site.rglob("*"):
        relative = item.relative_to(site).as_posix()
        require(not item.is_symlink(), "symlink_not_permitted")
        require(item.is_file() or item.is_dir(), "unsupported_file_type")
        if item.is_file():
            actual.add(relative)
    require(actual == set(expected), "unexpected_or_missing_public_asset")
    total = 0
    for name, data in expected.items():
        item = site / name
        require(item.is_file() and not item.is_symlink(), "untrusted_asset")
        raw = item.read_bytes()
        require(raw == data, "reviewed_asset_byte_mismatch")
        total += len(raw)
    require(10000 < total <= 150000, "unexpected_site_size")
    receipt = json.loads((site / "nexus-stage23-integrity.json").read_bytes())
    require(receipt.get("status") == "STATIC_ARTIFACT_NOT_HOSTED",
            "inaccurate_embedded_claim")
    require(receipt.get("public_deployment_proven") is False
            and receipt.get("actual_mobile_tested") is False
            and receipt.get("railway_original_volume_restored") is False,
            "unreviewed_assertions")
    return {
        "schema": "nexus.stage24.static-only-site.v1",
        "status": "LOCAL_STATIC_BYTES_PASS",
        "file_count": len(actual), "bytes": total,
        "has_only_reviewed_assets": True,
        "index_sha256": hashlib.sha256(expected["index.html"]).hexdigest(),
        "service_worker_sha256":
            hashlib.sha256(expected["service-worker.js"]).hexdigest(),
        "verified_public_https": False, "owner_android_tested": False,
        "railway_original_volume_recovery_proven": False,
        "human_judgment_authority": "human",
    }


def verify_response(status: int, mime: str, body: bytes, relative: str,
                    expected: bytes) -> dict:
    require(relative in ALLOWED_MIME, "unapproved_public_path")
    kind = mime.lower().split(";", 1)[0].strip()
    require(status == 200, "not_http_200")
    require(kind in ALLOWED_MIME[relative], "unexpected_content_type")
    require(0 < len(body) <= 150000, "invalid_remote_response_length")
    require(body == expected, "remote_bytes_do_not_match_reviewed_build")
    return {
        "asset": relative or "/", "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "exact_byte_match": True, "mime": kind,
    }


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def verified_url(relative: str) -> str:
    require(relative in PUBLIC_FILES, "unapproved_public_asset")
    url = urllib.parse.urljoin(PAGES_URL, relative)
    parsed = urllib.parse.urlparse(url)
    require(parsed.scheme == "https"
            and parsed.netloc == "maghsoodsaadatmerikation-sudo.github.io"
            and parsed.path.startswith("/nexus/")
            and not parsed.query and not parsed.fragment,
            "unapproved_public_host_or_path")
    return url


def verify_public(expected: dict[str, bytes]) -> dict:
    opener = urllib.request.build_opener(
        NoRedirect(), urllib.request.ProxyHandler({}))
    result = []
    for name in PUBLIC_FILES:
        source = "index.html" if name == "" else name
        req = urllib.request.Request(verified_url(name),
            headers={"Accept": "*/*", "Accept-Encoding": "identity",
                     "User-Agent": "NEXUS-Static-ReadOnly-Observer/24"},
            method="GET")
        try:
            with opener.open(req, timeout=12) as response:
                length = int(response.headers.get("Content-Length", "0") or 0)
                require(length <= 150000, "oversized_remote_content")
                raw = response.read(150001)
                result.append(verify_response(
                    response.status,
                    response.headers.get("Content-Type", ""),
                    raw, name, expected[source]))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            raise Refused("public_asset_unavailable_or_invalid") from None
    return {
        "schema": "nexus.stage24.public-https-observation.v1",
        "status": "PUBLIC_STATIC_BYTES_PASS",
        "origin": PAGES_URL,
        "checks": result,
        "exact_expected_count": len(PUBLIC_FILES),
        "verified_public_https": True,
        "owner_android_tested": False,
        "authenticated_rust_gateway_tested": False,
        "production_railway_volume_recovery_proven": False,
        "release_seal": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True, type=Path)
    parser.add_argument("--public", action="store_true",
                        help="GET fixed repo Pages origin ONLY; no credentials")
    args = parser.parse_args()
    try:
        source_pins()
        builder = stage23_builder()
        expected = builder.produce()
        local = validate_site(args.site, expected)
        output = verify_public(expected) if args.public else local
        print(json.dumps(output, separators=(",", ":"), sort_keys=True))
        return 0
    except (Refused, OSError, subprocess.SubprocessError, ValueError) as exc:
        status = "PUBLIC_NOT_VERIFIED" if args.public else "LOCAL_STATIC_BLOCKED"
        print(json.dumps({
            "schema": "nexus.stage24.fail-closed.v1",
            "status": status, "reason": str(exc)[:90].replace("/", "_"),
            "published": False, "release_seal": False,
        }, separators=(",", ":"), sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
