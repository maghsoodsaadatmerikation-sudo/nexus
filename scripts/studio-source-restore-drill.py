#!/usr/bin/env python3
"""Safely reconstitute a verified *public-source* Studio ZIP in disposable space.

No Render API, production deployment, user browser storage or owner secrets.
A restored source tree is NOT the Render build-artifact rollback capability.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import zipfile

from studio_public_assets import HISTORICAL_LIVE_FILES as FILES, asset_limit, check_historical_live_tree

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "nexus_source_fallback_for_restore", HERE / "studio-live-source-fallback.py"
)
fallback = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fallback)

SCHEMA = "nexus.studio.local-source-restore-drill.v1"
MAX_REPORT = 4000


def digest(data):
    return hashlib.sha256(data).hexdigest()


def restored_tree(directory):
    """Only the exact 17 reviewed paths may exist under public/studio."""
    dest = Path(directory) / "public" / "studio"
    found = check_historical_live_tree(dest)
    return {name: found[name].read_bytes() for name in FILES}


def verify_restored(directory, archive, manifest_path):
    """Fail closed even if a restored tree was altered after extraction."""
    witness = fallback.verify(archive, manifest_path)
    tree = restored_tree(directory)
    assert set(tree) == set(FILES)  # stronger checked path validation above
    for name in FILES:
        actual = tree[name]
        expected = witness["source_assets"][name]
        if len(actual) != expected["bytes"] or digest(actual) != expected["sha256"]:
            raise ValueError("restored byte mismatch")
    if b"const EXPECTED_SHA256='" + digest(tree["index.html"]).encode() + b"'" not in tree["service-worker.js"]:
        raise ValueError("restored service-worker HTML pin mismatch")
    return witness


def restore(archive, manifest_path, dest, report_path):
    # The source ZIP and report must have passed independent verification,
    # including 17 exact member names, original source SHA and ZIP SHA256.
    witness = fallback.verify(archive, manifest_path)
    target = fallback.gate.path_is_new_external(dest)
    report = fallback.gate.path_is_new_external(report_path)
    if target == report or report.is_relative_to(target) or target.is_relative_to(report):
        raise ValueError("outputs cannot contain or overlap one another")
    # Explicit new temporary output. Never follow ZIP paths, symlinks or
    # extractall: create only the reviewed names and minimal directories.
    target.mkdir(mode=0o700)
    try:
        root = target / "public" / "studio"
        root.mkdir(parents=True, mode=0o700)
        with zipfile.ZipFile(archive, "r", allowZip64=False) as zipped:
            for name in FILES:
                member = fallback.BUNDLE + "/" + name
                data = zipped.read(member)
                assert 0 < len(data) <= asset_limit(name)
                item = root / name
                item.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                # Prevent accidental overwrite and reject non-regular files.
                with item.open("xb") as dst:
                    dst.write(data)
                item.chmod(0o600)
        verify_restored(target, archive, manifest_path)
        record = {
            "schema": SCHEMA,
            "source_commit": witness["source_commit"],
            "render_deploy_id_at_snapshot": witness["current_live_deploy_at_snapshot"],
            "source_archive_sha256": witness["archive_sha256"],
            "restored_public_files": len(FILES),
            "restored_html_sha256": witness["source_assets"]["index.html"]["sha256"],
            "source_exact_bytes_reconstituted": True,
            "tested_context": "disposable_local_source_only",
            "real_browser_tested_by_this_step": False,
            "render_build_artifact_retained_confirmed": False,
            "actual_render_rollback_executed": False,
            "real_user_archive_recovered": False,
            "production_deployment_performed": False,
            "provider_credentials_used": False,
            "private_user_data_used": False,
            "authority": "none",
        }
        payload = (json.dumps(record, sort_keys=True, separators=(",", ":"))+"\n").encode("ascii")
        if len(payload) > MAX_REPORT:
            raise ValueError("unexpected restore report size")
        with report.open("xb") as output:
            output.write(payload)
        return record
    except Exception:
        # Destination was guaranteed absent before this function created it.
        # Never delete external content from a user-supplied pre-existing dir.
        shutil.rmtree(target)
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--restore", action="store_true")
    mode.add_argument("--verify", action="store_true")
    p.add_argument("--zip", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--dest", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    try:
        if args.restore:
            result = restore(args.zip, args.manifest, args.dest, args.report)
        else:
            witness = verify_restored(args.dest, args.zip, args.manifest)
            candidate = json.loads(args.report.read_bytes())
            if (args.report.is_symlink() or not args.report.is_file() or
                    args.report.stat().st_size > MAX_REPORT or
                    candidate.get("schema") != SCHEMA or
                    candidate.get("source_commit") != witness["source_commit"] or
                    candidate.get("render_deploy_id_at_snapshot") != witness["current_live_deploy_at_snapshot"] or
                    candidate.get("source_archive_sha256") != witness["archive_sha256"] or
                    candidate.get("restored_public_files") != len(FILES) or
                    candidate.get("restored_html_sha256") != witness["source_assets"]["index.html"]["sha256"] or
                    candidate.get("source_exact_bytes_reconstituted") is not True or
                    candidate.get("tested_context") != "disposable_local_source_only" or
                    any(candidate.get(field) is not False for field in (
                        "real_browser_tested_by_this_step",
                        "render_build_artifact_retained_confirmed",
                        "actual_render_rollback_executed", "real_user_archive_recovered",
                        "production_deployment_performed", "provider_credentials_used",
                        "private_user_data_used",
                    )) or candidate.get("authority") != "none" or
                    set(candidate) != {
                        "schema", "source_commit", "render_deploy_id_at_snapshot",
                        "source_archive_sha256", "restored_public_files",
                        "restored_html_sha256", "source_exact_bytes_reconstituted",
                        "tested_context", "real_browser_tested_by_this_step",
                        "render_build_artifact_retained_confirmed",
                        "actual_render_rollback_executed", "real_user_archive_recovered",
                        "production_deployment_performed", "provider_credentials_used",
                        "private_user_data_used", "authority",
                    }):
                raise ValueError("unreviewed restore evidence")
            result = candidate
        print(json.dumps({
            "status": "RESTORED_SOURCE_BYTES_VERIFIED",
            "restored_public_files": result["restored_public_files"],
            "source_commit": result["source_commit"],
            "authority": "none",
            "actual_render_rollback_executed": False,
        }, sort_keys=True))
        return 0
    except (OSError, TypeError, ValueError, KeyError, AssertionError,
            json.JSONDecodeError, zipfile.BadZipFile):
        print("STUDIO LOCAL SOURCE RESTORE: BLOCKED; NO PROVIDER RESTORATION", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
