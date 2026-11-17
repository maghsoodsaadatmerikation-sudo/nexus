#!/usr/bin/env python3
"""Preserve the actual live NEXUS Studio public code as an independent fallback.

This tool has no Render credentials, no deployment/rollback action, no private
user data and no claim of provider build artifact retention. It copies only a
fixed, reviewed Git source commit after matching the actual public HTTPS bytes.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "studio-static-release-gate.py"
_spec = importlib.util.spec_from_file_location("nexus_static_release_gate", SCRIPT)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

LIVE_COMMIT = "560badfa977f6ed1e1298388ee1ce3650ebc9daa"
LIVE_DEPLOY = "dep-dbrle58n74is73971t0g"
SERVICE = "srv-dbrjurc9v7es73cqe0v0"
WORKSPACE = "tea-dabhioe10ojc73acbs8g"
SCHEMA = "nexus.studio.live-source-fallback.v1"
BUNDLE = "nexus-studio-previous-live-source"
MAX_RESULT = 10_000


def sha(data):
    return hashlib.sha256(data).hexdigest()


def check_old_root(root):
    root = Path(root).resolve(strict=True)
    rev = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, timeout=8, text=True).strip()
    if rev != LIVE_COMMIT:
        raise ValueError("BLOCKED: old checkout does not match known live Git SHA")
    source = root / "public/studio"
    found = sorted(str(p.relative_to(source)) for p in source.rglob("*") if p.is_file())
    if found != sorted(gate.FILES):
        raise ValueError("BLOCKED: historical source asset list differs")
    assets = {}
    for name in gate.FILES:
        target = source / name
        st = target.lstat()
        if target.is_symlink() or not stat.S_ISREG(st.st_mode) or \
                st.st_nlink != 1 or not (0 < st.st_size <= gate.MAX_FILE):
            raise ValueError("BLOCKED: unsafe historical asset")
        assets[name] = target.read_bytes()
    if b"const EXPECTED_SHA256='" + sha(assets["index.html"]).encode() + b"'" not in \
            assets["service-worker.js"]:
        raise ValueError("BLOCKED: historical worker does not pin historical HTML")
    return assets


def compare_live(assets, fetch=None):
    fetch = fetch or gate.live_fetch
    statuses = {}
    for name in gate.OBSERVE:
        try:
            current = fetch(name)
        except Exception:
            statuses[name] = "UNREACHABLE"
        else:
            statuses[name] = "MATCH" if current == assets[name] else "DRIFT"
    return statuses


def archive(assets, target):
    target = gate.path_is_new_external(target)
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_STORED,
                         allowZip64=False) as dst:
        for name in sorted(assets):
            info = zipfile.ZipInfo(f"{BUNDLE}/{name}", date_time=gate.STAMP)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_STORED
            dst.writestr(info, assets[name])
    return target


def make_report(assets, statuses, zip_sha):
    if set(statuses) != set(gate.OBSERVE):
        raise ValueError("BLOCKED: incomplete public observation")
    if set(assets) != set(gate.FILES):
        raise ValueError("BLOCKED: unexpected fallback asset set")
    if not re.fullmatch(r"[0-9a-f]{64}", zip_sha):
        raise ValueError("BLOCKED: invalid package digest")
    return {
        "schema": SCHEMA,
        "live_service_id_at_snapshot": SERVICE,
        "render_workspace_id_at_snapshot": WORKSPACE,
        "current_live_deploy_at_snapshot": LIVE_DEPLOY,
        "source_commit": LIVE_COMMIT,
        "origin": gate.ORIGIN,
        "origin_matches_pinned_live_source": all(s == "MATCH" for s in statuses.values()),
        "observed_paths": [{"path": name, "status": statuses[name]}
                           for name in gate.OBSERVE],
        "reviewed_file_count": len(gate.FILES),
        "source_assets": {name: {"bytes": len(assets[name]), "sha256": sha(assets[name])}
                          for name in sorted(assets)},
        "archive_sha256": zip_sha,
        "data_included": "public_static_source_only",
        "rollback_render_build_artifact_confirmed": False,
        "rollback_action_available_in_connector": False,
        "actual_rollback_executed": False,
        "production_deploy_executed": False,
        "real_user_archive_recovered": False,
        "no_new_service_or_cost": True,
        "authority": "none",
    }


def build(old_root, dest_zip, dest_report, fetch=None):
    dest_zip = gate.path_is_new_external(dest_zip)
    dest_report = gate.path_is_new_external(dest_report)
    if dest_zip == dest_report:
        raise ValueError("BLOCKED: outputs share same path")
    assets = check_old_root(old_root)
    statuses = compare_live(assets, fetch)
    if any(value != "MATCH" for value in statuses.values()):
        raise ValueError("BLOCKED: live public HTML/worker/assets do not match proposed fallback")
    try:
        archive(assets, dest_zip)
        result = make_report(assets, statuses, sha(dest_zip.read_bytes()))
        dest_report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    except Exception:
        if dest_zip.is_file():
            dest_zip.unlink()
        if dest_report.is_file():
            dest_report.unlink()
        raise
    verify(dest_zip, dest_report)
    return result


def verify(zip_path, manifest_path):
    zip_path, manifest_path = Path(zip_path), Path(manifest_path)
    if zip_path.is_symlink() or not zip_path.is_file() or \
            zip_path.stat().st_size > gate.MAX_ZIP or \
            manifest_path.is_symlink() or not manifest_path.is_file() or \
            manifest_path.stat().st_size > MAX_RESULT:
        raise ValueError("BLOCKED: invalid fallback files")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schema") != SCHEMA or manifest.get("source_commit") != LIVE_COMMIT or \
            manifest.get("origin") != gate.ORIGIN or \
            manifest.get("origin_matches_pinned_live_source") is not True or \
            manifest.get("current_live_deploy_at_snapshot") != LIVE_DEPLOY or \
            manifest.get("authority") != "none" or \
            manifest.get("actual_rollback_executed") is not False or \
            manifest.get("production_deploy_executed") is not False or \
            manifest.get("rollback_render_build_artifact_confirmed") is not False or \
            manifest.get("archive_sha256") != sha(zip_path.read_bytes()) or \
            manifest.get("reviewed_file_count") != len(gate.FILES):
        raise ValueError("BLOCKED: fallback evidence/authority invalid")
    with zipfile.ZipFile(zip_path) as zipped:
        infos = zipped.infolist()
        if len(infos) != len(gate.FILES):
            raise ValueError("BLOCKED: unexpected fallback member count")
        assets = {}
        for member in infos:
            if not member.filename.startswith(BUNDLE + "/") or \
                    member.filename[len(BUNDLE)+1:] not in gate.FILES or \
                    member.filename in assets or \
                    member.is_dir() or member.compress_type != zipfile.ZIP_STORED or \
                    not stat.S_ISREG(member.external_attr >> 16) or \
                    member.file_size > gate.MAX_FILE:
                raise ValueError("BLOCKED: unsafe fallback entry")
            assets[member.filename[len(BUNDLE)+1:]] = zipped.read(member)
    expected = {name: {"bytes": len(data), "sha256": sha(data)}
                for name, data in sorted(assets.items())}
    if manifest.get("source_assets") != expected:
        raise ValueError("BLOCKED: fallback ZIP asset hashes differ")
    observed = manifest.get("observed_paths")
    if not isinstance(observed, list) or observed != [
        {"path": name, "status": "MATCH"} for name in gate.OBSERVE
    ]:
        raise ValueError("BLOCKED: missing public live source match")
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    options = p.add_mutually_exclusive_group(required=True)
    options.add_argument("--build", action="store_true")
    options.add_argument("--verify", action="store_true")
    p.add_argument("--old-root", type=Path)
    p.add_argument("--zip", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    try:
        if args.build:
            if not args.old_root:
                raise ValueError("BLOCKED: source checkout is required")
            result = build(args.old_root, args.zip, args.report)
            print("LIVE STATIC SOURCE FALLBACK VERIFIED, NO DEPLOY: " + result["archive_sha256"])
        else:
            verify(args.zip, args.report)
            print("SOURCE FALLBACK ZIP INTEGRITY: PASS (not production restoration)")
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError,
            json.JSONDecodeError, zipfile.BadZipFile) as e:
        print("LIVE FALLBACK: BLOCKED (" + type(e).__name__ + ")", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
