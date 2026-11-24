#!/usr/bin/env python3
"""Read-only complete current-inventory public Studio source observation.

Unlike the legacy nine-asset pre-promotion observer this also checks the
reviewed PDF worker, PDF modules and license files. The report is only source
parity evidence: it never attests Render deploy ID, rollback availability,
Android user archives or approval to promote. No provider token is loaded.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

from png_pixels import pixel_digest
from studio_public_assets import FILES, asset_limit

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "nexus_public_candidate_gate", HERE / "studio-static-release-gate.py"
)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

SCHEMA = "nexus.studio.full-public-source-observation.v1"
MAX_REPORT = 12000
ICON_DIMENSIONS = {"icons/nexus-192.png": 192, "icons/nexus-512.png": 512}
SHAS = re.compile(r"[0-9a-f]{40}\Z")


def mime_types(name):
    """Strict fixed MIME types; never infer an arbitrary endpoint from a URL."""
    if name == "index.html":
        return {"text/html"}
    if name == "manifest.json":
        return {"application/json", "application/manifest+json"}
    if name in ICON_DIMENSIONS:
        return {"image/png"}
    if name.endswith(".json"):
        return {"application/json"}
    if name.endswith((".js", ".mjs")):
        return {"text/javascript", "application/javascript"}
    if name.endswith(".txt"):
        return {"text/plain"}
    raise ValueError("asset type is not in the reviewed public inventory")


def fetch_live(name):
    """GET only the source-reviewed fixed origin; no redirects or credentials."""
    if name not in FILES:
        raise ValueError("unreviewed public asset")
    path = "" if name == "index.html" else name
    req = urllib.request.Request(
        gate.ORIGIN + path,
        method="GET",
        headers={
            "User-Agent": "NEXUS-Studio-Complete-Source-Observer/1.0",
            "Accept": "*/*",
            "Accept-Encoding": "identity",
        },
    )
    opener = urllib.request.build_opener(gate.NoRedirect())
    with opener.open(req, timeout=12) as response:
        if response.status != 200 or response.geturl() != req.full_url:
            raise ValueError("unexpected public HTTPS response")
        content_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if content_type not in mime_types(name):
            raise ValueError("unreviewed public MIME type")
        if response.headers.get("Content-Encoding", "identity").lower() != "identity":
            raise ValueError("content encoding not source-equivalent")
        data = response.read(asset_limit(name) + 1)
        if not 0 < len(data) <= asset_limit(name):
            raise ValueError("public asset missing or too large")
        return data


def inspect_assets(assets, source_commit, fetch=fetch_live):
    """Produce evidence from independently selected source bytes, without mutation.

    The public workflow calls this only after verifying the source ZIP and
    manifest at the exact checked-out Git commit. Tests inject synthetic HTTP
    responses instead of contacting the real site.
    """
    if (type(assets) is not dict or set(assets) != set(FILES)
            or not isinstance(source_commit, str)
            or not SHAS.fullmatch(source_commit)):
        raise ValueError("source inventory or commit not reviewed")
    if any(type(data) is not bytes or not 0 < len(data) <= asset_limit(name)
           for name, data in assets.items()):
        raise ValueError("unreviewed source bytes")

    records = []
    for name in FILES:
        try:
            live = fetch(name)
            if type(live) is not bytes or not 0 < len(live) <= asset_limit(name):
                raise ValueError("empty or over-limit public response")
            if live == assets[name]:
                status = "MATCH"
            elif name in ICON_DIMENSIONS:
                try:
                    px = ICON_DIMENSIONS[name]
                    status = ("PIXEL_MATCH" if pixel_digest(live, px, px)
                              == pixel_digest(assets[name], px, px) else "DRIFT")
                except (ValueError, TypeError, OverflowError):
                    status = "DRIFT"
            else:
                status = "DRIFT"
        except (OSError, ValueError, TypeError, urllib.error.URLError, TimeoutError):
            status = "UNREACHABLE"
        records.append({"path": name, "status": status})

    statuses = [item["status"] for item in records]
    if "UNREACHABLE" in statuses:
        result = "INCOMPLETE_PUBLIC_OBSERVATION"
    elif "DRIFT" in statuses:
        result = "PUBLIC_SOURCE_DRIFT"
    else:
        result = "SOURCE_MATCH_ONLY"
    return {
        "schema": SCHEMA,
        "source_commit": source_commit,
        "fixed_public_origin": gate.ORIGIN,
        "status": result,
        "reviewed_public_files": len(FILES),
        "observed_public_files": len(records),
        "assets": records,
        # Pure source-comparison helper alone does NOT authenticate a manifest.
        "source_manifest_verified": False,
        "read_only": True,
        "render_deploy_id_verified": False,
        "public_browser_verified": False,
        "real_android_device_verified": False,
        "provider_model_available_verified": False,
        "rollback_provider_artifact_verified": False,
        "production_promotion_authorized": False,
        "provider_mutation": False,
        "private_user_data_seen": False,
        "authority": "none",
    }


def observe_verified(zip_path, manifest_path, commit, fetch=fetch_live):
    """Verify both public ZIP and source manifest before ANY HTTPS request."""
    manifest = gate.verify(zip_path, manifest_path, expected_commit=commit)
    assets = gate.source_assets()
    # Explicit full manifest binding; fail before network on any source drift.
    expected = {name: {"bytes": len(data), "sha256": gate.sha(data)}
                for name, data in sorted(assets.items())}
    if manifest.get("assets") != expected:
        raise ValueError("candidate manifest and checkout disagree")
    result = inspect_assets(assets, commit, fetch=fetch)
    result["source_manifest_verified"] = True
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--zip", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--source-commit", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    try:
        target = gate.path_is_new_external(args.out)
        result = observe_verified(args.zip, args.manifest, args.source_commit)
        encoded = (json.dumps(result, ensure_ascii=True, sort_keys=True,
                              separators=(",", ":")) + "\n").encode("ascii")
        if len(encoded) > MAX_REPORT:
            raise ValueError("observation exceeded strict output cap")
        target.write_bytes(encoded)
        print(json.dumps({
            "status": result["status"],
            "source_commit": result["source_commit"],
            "observed_public_files": result["observed_public_files"],
            "authority": "none",
            "public_release_authorized": False,
        }, sort_keys=True))
        # A drift report is useful even if public has not been promoted.
        # The separate promotion decision MUST NOT turn this green into GO.
        return 0
    except (ValueError, TypeError, OSError, KeyError):
        print("COMPLETE PUBLIC SOURCE OBSERVATION: BLOCKED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
