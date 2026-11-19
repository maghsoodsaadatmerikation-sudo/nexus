#!/usr/bin/env python3
"""Public-only, source-bound NEXUS Studio static release candidate.

A source ZIP and immutable external manifest are for human inspection only.
Never deploys Render, mutates Railway, reads owner data or claims production
readiness. Public origin comparison is a bounded read-only observation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile

from studio_public_assets import FILES, MAX_FILE, check_public_tree

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "public/studio"
BUNDLE = "nexus-studio-static-site"
ORIGIN = "https://nexus-studio-merikation.onrender.com/"
SCHEMA = "nexus.studio.static-release-candidate.v1"
OBSERVATION_SCHEMA = "nexus.studio.public-release-observation.v1"
STAMP = (2020, 1, 1, 0, 0, 0)
# A returned MATCH on nine reviewed public assets is not a substitute for
# production owner-authorized release, nor the real public-origin browser tests.
OBSERVE = FILES[:9]
MAX_ZIP = 900_000


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_assets():
    subprocess.run([sys.executable, str(ROOT / "scripts/build-studio-static.py"), "--check"],
                   check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=60)
    assets = {name: path.read_bytes() for name, path in check_public_tree(SOURCE).items()}
    index = assets["index.html"]
    worker = assets["service-worker.js"]
    if b"const EXPECTED_SHA256='" + sha(index).encode() + b"'" not in worker or \
            b"nexus-studio-shell-v1-" not in worker or \
            b"manifest-src 'self'" not in index or \
            b"worker-src 'self' blob:" not in index:
        raise ValueError("candidate PWA source not hash bound")
    manifest = json.loads(assets["manifest.json"])
    if manifest.get("start_url") != "./" or manifest.get("scope") != "./" or \
            manifest.get("display") != "standalone":
        raise ValueError("invalid scoped static PWA")
    return assets


def path_is_new_external(path):
    path = Path(path)
    if not path.is_absolute() or path.exists() or path.is_symlink() or \
            path.is_relative_to(ROOT) or ROOT.is_relative_to(path) or \
            not path.parent.is_dir() or path.parent != path.parent.resolve():
        raise ValueError("output must be new, absolute, outside repository and canonical")
    return path


def archive_payloads(assets):
    return {BUNDLE + "/" + name: assets[name] for name in FILES}


def build(archive, manifest_path, commit):
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("exact 40-character source commit required")
    archive = path_is_new_external(archive)
    manifest_path = path_is_new_external(manifest_path)
    if archive == manifest_path:
        raise ValueError("archive and manifest cannot be same output")
    assets = source_assets()
    old_umask = os.umask(0o077)
    try:
        with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_STORED,
                             allowZip64=False) as zipped:
            for name, data in sorted(archive_payloads(assets).items()):
                info = zipfile.ZipInfo(name, date_time=STAMP)
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_STORED
                zipped.writestr(info, data)
        meta = {
            "schema": SCHEMA,
            "source_commit": commit,
            "zip_sha256": sha(archive.read_bytes()),
            "origin_to_compare": ORIGIN,
            "content_count": len(FILES),
            "assets": {
                name: {"bytes": len(data), "sha256": sha(data)}
                for name, data in sorted(assets.items())
            },
            "contains_private_data": False,
            "contains_provider_secrets": False,
            "render_deploy_performed": False,
            "android_hardware_tested": False,
            "production_promotion_authorized": False,
            "readiness": "REVIEW_CANDIDATE_ONLY",
            "authority": "none",
        }
        manifest_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
        verify(archive, manifest_path, expected_commit=commit)
    finally:
        os.umask(old_umask)
    return meta


def verify(archive, manifest_path, expected_commit=None):
    archive, manifest_path = Path(archive), Path(manifest_path)
    if not archive.is_file() or archive.is_symlink() or \
            archive.stat().st_size > MAX_ZIP or not manifest_path.is_file() or \
            manifest_path.is_symlink() or manifest_path.stat().st_size > 9000:
        raise ValueError("invalid candidate or release manifest")
    manifest = json.loads(manifest_path.read_bytes())
    commit = manifest.get("source_commit")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit) or \
            (expected_commit is not None and commit != expected_commit):
        raise ValueError("release source commit mismatch")
    if manifest.get("schema") != SCHEMA or manifest.get("readiness") != "REVIEW_CANDIDATE_ONLY" or \
            manifest.get("authority") != "none" or \
            manifest.get("production_promotion_authorized") is not False or \
            manifest.get("contains_private_data") is not False or \
            manifest.get("contains_provider_secrets") is not False or \
            manifest.get("render_deploy_performed") is not False or \
            manifest.get("android_hardware_tested") is not False or \
            manifest.get("origin_to_compare") != ORIGIN or \
            manifest.get("content_count") != len(FILES):
        raise ValueError("invalid/non-public release authority contract")
    expected = source_assets()
    asset_records = {
        name: {"bytes": len(data), "sha256": sha(data)}
        for name, data in sorted(expected.items())
    }
    if manifest.get("assets") != asset_records or \
            manifest.get("zip_sha256") != sha(archive.read_bytes()):
        raise ValueError("release manifest does not bind reviewed bytes")
    with zipfile.ZipFile(archive, "r", allowZip64=False) as zipped:
        found = {}
        infos = zipped.infolist()
        if len(infos) != len(FILES):
            raise ValueError("unexpected ZIP member count")
        for info in infos:
            prefix = BUNDLE + "/"
            if not info.filename.startswith(prefix):
                raise ValueError("unexpected root in release candidate")
            relative = info.filename[len(prefix):]
            if relative not in FILES or relative in found or \
                    ".." in PurePosixPath(relative).parts or \
                    info.file_size > MAX_FILE or info.is_dir() or \
                    info.flag_bits & 1 or info.compress_type != zipfile.ZIP_STORED or \
                    not stat.S_ISREG(info.external_attr >> 16):
                raise ValueError("unreviewed ZIP member")
            found[relative] = zipped.read(info)
        if found != expected:
            raise ValueError("candidate bytes differ from reviewed source")
    return manifest


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, url):
        return None


def live_fetch(name):
    if name not in OBSERVE:
        raise ValueError("public observation can only GET allowed fixed assets")
    # Fixed, manually reviewed origin. Do not accept user-provided URL or token.
    request = urllib.request.Request(
        ORIGIN + ("" if name == "index.html" else name),
        headers={"User-Agent": "NEXUS-Static-Source-Witness/1.0",
                 "Accept": "*/*"},
        method="GET")
    response = NoRedirect()
    opener = urllib.request.build_opener(response)
    with opener.open(request, timeout=12) as res:
        if res.status != 200 or res.geturl() != request.full_url:
            raise ValueError("unexpected public origin response or redirect")
        data = res.read(MAX_FILE + 1)
        if len(data) > MAX_FILE:
            raise ValueError("public response too large")
        kind = (res.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        expected_kind = (
            {"index.html": ("text/html",),
             "manifest.json": ("application/json", "application/manifest+json"),
             "service-worker.js": ("text/javascript", "application/javascript")}
            .get(name, ("image/png",) if name.endswith(".png") else
                 ("application/json",) if name.endswith(".json") else
                 ("text/javascript", "application/javascript")))
        if kind not in expected_kind:
            raise ValueError("unexpected public MIME")
        return data


def observe_public(manifest, fetch=live_fetch):
    if manifest.get("schema") != SCHEMA or manifest.get("authority") != "none" or \
            manifest.get("readiness") != "REVIEW_CANDIDATE_ONLY" or \
            manifest.get("origin_to_compare") != ORIGIN or \
            manifest.get("production_promotion_authorized") is not False or \
            manifest.get("render_deploy_performed") is not False or \
            manifest.get("contains_private_data") is not False or \
            manifest.get("contains_provider_secrets") is not False or \
            not isinstance(manifest.get("source_commit"), str) or \
            not re.fullmatch(r"[0-9a-f]{40}", manifest["source_commit"]):
        raise ValueError("untrusted release comparison source")
    # A user-supplied external JSON must never redefine the expected public
    # source identity. The observer independently derives the exact reviewed
    # bytes again and fails closed if the manifest is forged or stale.
    reviewed = source_assets()
    evidence = {
        name: {"bytes": len(data), "sha256": sha(data)}
        for name, data in sorted(reviewed.items())
    }
    if manifest.get("assets") != evidence or manifest.get("content_count") != len(FILES):
        raise ValueError("unreviewed manifest cannot establish public source identity")
    records = []
    for name in OBSERVE:
        expected = manifest["assets"][name]
        try:
            actual = fetch(name)
            status = "MATCH" if len(actual) == expected["bytes"] and \
                    sha(actual) == expected["sha256"] else "DRIFT"
        except (OSError, ValueError, urllib.error.URLError, TimeoutError):
            status = "UNREACHABLE"
        records.append({"name": name, "status": status})
    if all(x["status"] == "MATCH" for x in records):
        status = "SOURCE_MATCH_ONLY"
    elif any(x["status"] == "UNREACHABLE" for x in records):
        status = "INCOMPLETE_PUBLIC_OBSERVATION"
    else:
        status = "PUBLIC_SOURCE_DRIFT"
    return {
        "schema": OBSERVATION_SCHEMA,
        "source_commit": manifest["source_commit"],
        "fixed_public_origin": ORIGIN,
        "status": status,
        "assets": records,
        "observed_asset_count": len(records),
        "actual_deploy_identified": False,
        "real_browser_offline_verified": False,
        "production_promotion_authorized": False,
        "render_deploy_performed": False,
        "read_only": True,
        "authority": "none",
    }


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    modes = cli.add_mutually_exclusive_group(required=True)
    modes.add_argument("--build", action="store_true")
    modes.add_argument("--verify", action="store_true")
    modes.add_argument("--observe-public", action="store_true")
    cli.add_argument("--zip", type=Path)
    cli.add_argument("--manifest", type=Path, required=True)
    cli.add_argument("--source-commit")
    cli.add_argument("--report", type=Path)
    args = cli.parse_args()
    try:
        if args.build:
            if not args.zip or not args.source_commit:
                raise ValueError("ZIP and source commit required")
            meta = build(args.zip, args.manifest, args.source_commit)
            print("STATIC STUDIO REVIEW CANDIDATE: PASS " + meta["zip_sha256"])
        elif args.verify:
            if not args.zip:
                raise ValueError("ZIP required")
            verify(args.zip, args.manifest, args.source_commit)
            print("STATIC STUDIO SOURCE-BOUND REVIEW ZIP: PASS")
        else:
            if args.report is None:
                raise ValueError("report path required")
            report_path = path_is_new_external(args.report)
            manifest = json.loads(args.manifest.read_bytes())
            report = observe_public(manifest)
            report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
            print("PUBLIC STUDIO READ-ONLY STATUS: " + report["status"])
            print("No release was performed; public source drift is expected before authorized promotion.")
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError,
            zipfile.BadZipFile, json.JSONDecodeError) as e:
        print("STATIC STUDIO RELEASE GATE: BLOCKED (" + type(e).__name__ + ")", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
