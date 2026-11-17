#!/usr/bin/env python3
"""Validate independently observed public Studio acceptance without deploy authority.

Consumes read-only GitHub Actions public observation reports; all private test
data are synthetic. This is a verification witness, not a Render deploy ID,
owner Android test, credential check or authorization to release.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
ORIGIN = "https://nexus-studio-merikation.onrender.com/"
SCHEMA = "nexus.studio.public-post-promotion-witness.v1"
REQUIRED_CHECKS = frozenset({
    "encrypted-browser-save",
    "true-offline-reload-still-locked",
    "offline-encrypted-reopen",
    "corrupted-offline-shell-rejected",
    "remove-code-retains-open-and-encrypted-work",
})
ASSET_KEYS = (
    "/", "/manifest.json", "/service-worker.js",
    "/icons/nexus-192.png", "/icons/nexus-512.png",
    "/device/device-engine.js", "/device/device-worker.js",
    "/device/device-ui.js", "/device/model-manifest.json",
)


class WitnessError(ValueError):
    pass


def load_json(path):
    source = Path(path)
    if source.is_symlink() or not source.is_file() or source.stat().st_size > 35000:
        raise WitnessError("missing/oversized witness")
    obj = json.loads(source.read_bytes())
    if not isinstance(obj, dict):
        raise WitnessError("expected JSON record")
    return obj


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_assets(assets, expected_hash):
    if assets.get("status") != "PASS" or assets.get("origin") != ORIGIN.rstrip("/") or \
            assets.get("authority") != "none" or assets.get("production_mutation") is not False or \
            assets.get("user_data_seen") is not False or \
            assets.get("server_credentials_used") is not False or \
            assets.get("verified_resources") != len(ASSET_KEYS):
        raise WitnessError("public HTTPS source identity not confirmed")
    resources = assets.get("resources")
    if not isinstance(resources, dict) or set(resources) != set(ASSET_KEYS):
        raise WitnessError("public source asset count/paths mismatch")
    for name in ASSET_KEYS:
        item = resources[name]
        if not isinstance(item, dict) or item.get("ok") is not True or \
                item.get("http_status") != 200:
            raise WitnessError("public source asset unavailable")
        if name not in ("/icons/nexus-192.png", "/icons/nexus-512.png"):
            if item.get("exact_byte_match") is not True:
                raise WitnessError("public source bytes not exact")
        else:
            if item.get("pixel_match") is not True:
                raise WitnessError("public icon pixel identity not exact")
    if resources["/"].get("expected_sha256") != expected_hash or \
            resources["/"].get("sha256") != expected_hash:
        raise WitnessError("public root HTML not exact-source reviewed")
    return {"checked_public_paths": len(ASSET_KEYS), "public_root_sha256": expected_hash}


def checked_browser(report, expected_hash):
    if report.get("status") != "PASS" or report.get("origin") != ORIGIN or \
            report.get("source_sha256") != expected_hash or \
            report.get("actual_offline_navigation") is not True or \
            report.get("real_android_hardware") is not False or \
            report.get("real_model_tested") is not False or report.get("authority") != "none":
        raise WitnessError("real public browser acceptance not confirmed")
    checks = report.get("checks")
    if not isinstance(checks, list) or len(checks) < 15 or \
            len(checks) != len(set(checks)) or \
            not all(isinstance(c, str) for c in checks) or \
            not REQUIRED_CHECKS.issubset(checks):
        raise WitnessError("public Chromium acceptance incomplete")
    return tuple(checks)


def checked_model(report, manifest):
    if report.get("status") != "PASS" or report.get("origin") != ORIGIN or \
            report.get("real_model_tested") is not True or \
            report.get("real_android_hardware") is not False or \
            report.get("authority") != "none" or \
            report.get("model") != manifest.get("model") or \
            report.get("revision") != manifest.get("revision") or \
            report.get("runtime") != manifest.get("runtime"):
        raise WitnessError("public real-model witness incomplete")
    checks = report.get("checks")
    required = {"actual-model-uses-supplied-fact-in-english",
                "browser-network-offline-before-inference",
                "actual-inference-report-excludes-answer-text",
                "cancel-terminates-real-inference-worker"}
    if not isinstance(checks, list) or len(checks) != len(set(checks)) or \
            not required.issubset(checks):
        raise WitnessError("public model behavior not demonstrated")
    if not isinstance(report.get("download_bytes"), int) or \
            report["download_bytes"] < 1_000_000:
        raise WitnessError("real weights not observed")
    # The generator's synthetic answer is not needed in release acceptance.
    # Never put it into the exported dossier.
    return {"model": manifest["model"], "revision": manifest["revision"],
            "runtime": manifest["runtime"], "model_checks": len(checks)}


def build_report(assets, browser1, browser2, model, source_sha, model_manifest,
                 *, commit):
    if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise WitnessError("exact pinned Git source SHA required")
    checked = checked_assets(assets, source_sha)
    first = checked_browser(browser1, source_sha)
    second = checked_browser(browser2, source_sha)
    if first != second:
        raise WitnessError("two fresh Chromium runs disagree in checked behaviors")
    checked.update(checked_model(model, model_manifest))
    return {
        "schema": SCHEMA,
        "source_commit": commit,
        "fixed_public_origin": ORIGIN,
        "status": "PUBLIC_CHROMIUM_ACCEPTED",
        "source_sha256": checked["public_root_sha256"],
        "checked_public_paths": checked["checked_public_paths"],
        "independent_fresh_chromium_runs": 2,
        "browser_checks_per_run": len(first),
        "both_runs_reopened_encrypted_archive_offline": True,
        "both_runs_rejected_corrupted_cache": True,
        "tested_local_model": checked["model"],
        "pinned_model_revision": checked["revision"],
        "model_runtime": checked["runtime"],
        "model_checks": checked["model_checks"],
        "actual_render_deploy_id_verified": False,
        "render_deploy_performed": False,
        "real_android_hardware_verified": False,
        "production_seal": False,
        "private_user_data_used": False,
        "provider_token_used": False,
        "owner_promotion_authorized": False,
        "authority": "none",
    }


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--assets", type=Path, required=True)
    cli.add_argument("--browser-first", type=Path, required=True)
    cli.add_argument("--browser-second", type=Path, required=True)
    cli.add_argument("--model", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--source-commit", required=True)
    args = cli.parse_args()
    try:
        if args.output.exists() or args.output.is_symlink():
            raise WitnessError("never overwrite an existing public witness")
        expected_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, timeout=5).strip()
        if args.source_commit != expected_sha:
            raise WitnessError("witness must refer to exact checked-out Git commit")
        source_sha = digest(ROOT / "public/studio/index.html")
        manifest = json.loads((ROOT / "public/studio/device/model-manifest.json").read_text())
        result = build_report(
            load_json(args.assets), load_json(args.browser_first),
            load_json(args.browser_second), load_json(args.model),
            source_sha, manifest, commit=args.source_commit)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print("PUBLIC STUDIO OBSERVED: PASS - independent Chromium witness only")
    except (WitnessError, OSError, TypeError, KeyError, json.JSONDecodeError,
            subprocess.SubprocessError) as error:
        print("PUBLIC STUDIO WITNESS: BLOCKED (" + type(error).__name__ + ")",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
