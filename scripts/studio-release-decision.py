#!/usr/bin/env python3
"""Source-locked Studio release decision: read-only, permanently fail-safe HOLD.

Consumes the exact source ZIP/manifest and the complete current-inventory fixed-origin
observation from the same reviewed commit. Reports actionable blockers without
ever authorizing Render, Railway, model billing or public deployment.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys

from studio_public_assets import FILES

HERE = Path(__file__).resolve().parent
GATE = HERE / "studio-static-release-gate.py"
spec = importlib.util.spec_from_file_location("nexus_release_candidate_gate", GATE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

FULL_SCHEMA = "nexus.studio.full-public-source-observation.v1"
DECISION_SCHEMA = "nexus.studio.release-decision-hold.v1"
ORIGIN = gate.ORIGIN
SHA = re.compile(r"[0-9a-f]{40}\Z")
OBS_FIELDS = frozenset({
    "schema", "source_commit", "fixed_public_origin", "status",
    "reviewed_public_files", "observed_public_files", "assets",
    "source_manifest_verified", "read_only", "render_deploy_id_verified",
    "public_browser_verified", "real_android_device_verified",
    "provider_model_available_verified", "rollback_provider_artifact_verified",
    "production_promotion_authorized", "provider_mutation",
    "private_user_data_seen", "authority",
})
ICONS = frozenset({"icons/nexus-192.png", "icons/nexus-512.png"})
STATUS = frozenset({"MATCH", "PIXEL_MATCH", "DRIFT", "UNREACHABLE"})
MAX_INPUT = 14000


class UntrustedReleaseEvidence(ValueError):
    pass


def require(value):
    if not value:
        raise UntrustedReleaseEvidence("invalid, stale or unreviewed release evidence")


def unique_keys(pairs):
    value = {}
    for k, v in pairs:
        require(k not in value)
        value[k] = v
    return value


def load_observation(path):
    p = Path(path)
    require(p.is_file() and not p.is_symlink() and 0 < p.stat().st_size <= MAX_INPUT)
    try:
        obj = json.loads(p.read_bytes().decode("utf-8"), object_pairs_hook=unique_keys)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise UntrustedReleaseEvidence("invalid observation JSON") from None
    require(type(obj) is dict)
    return obj


def evaluate(*, manifest, observation, source_commit):
    """Every outcome is a non-release HOLD, including a complete source MATCH.

    Revalidates all evidence fields independently: no unknown upstream fields
    can reclassify a drift, invent a release PASS or smuggle sensitive contents
    into a trusted report. Source manifest itself is verified by gate.verify.
    """
    require(type(manifest) is dict and manifest.get("schema") == gate.SCHEMA
            and manifest.get("source_commit") == source_commit
            and manifest.get("readiness") == "REVIEW_CANDIDATE_ONLY"
            and manifest.get("origin_to_compare") == ORIGIN
            and manifest.get("production_promotion_authorized") is False
            and manifest.get("render_deploy_performed") is False
            and manifest.get("authority") == "none")
    require(type(source_commit) is str and SHA.fullmatch(source_commit))
    require(type(observation) is dict and set(observation) == OBS_FIELDS)
    require(observation["schema"] == FULL_SCHEMA
            and observation["source_commit"] == source_commit
            and observation["fixed_public_origin"] == ORIGIN
            and observation["reviewed_public_files"] == len(FILES)
            and observation["observed_public_files"] == len(FILES)
            and observation["source_manifest_verified"] is True
            and observation["read_only"] is True
            and observation["render_deploy_id_verified"] is False
            and observation["public_browser_verified"] is False
            and observation["real_android_device_verified"] is False
            and observation["provider_model_available_verified"] is False
            and observation["rollback_provider_artifact_verified"] is False
            and observation["production_promotion_authorized"] is False
            and observation["provider_mutation"] is False
            and observation["private_user_data_seen"] is False
            and observation["authority"] == "none"
            and type(observation["status"]) is str)
    assets = observation["assets"]
    require(type(assets) is list and len(assets) == len(FILES))
    problems = []
    for expected, record in zip(FILES, assets):
        require(type(record) is dict and set(record) == {"path", "status"})
        require(record["path"] == expected and type(record["status"]) is str
                and record["status"] in STATUS
                and (record["status"] != "PIXEL_MATCH" or expected in ICONS))
        if record["status"] in {"DRIFT", "UNREACHABLE"}:
            problems.append({"path": expected, "result": record["status"]})

    if any(p["result"] == "UNREACHABLE" for p in problems):
        observed = "INCOMPLETE_PUBLIC_OBSERVATION"
        hold = "HOLD_PUBLIC_OBSERVATION_INCOMPLETE"
        blocker = "PUBLIC_ASSET_UNREACHABLE"
    elif problems:
        observed = "PUBLIC_SOURCE_DRIFT"
        hold = "HOLD_PUBLIC_SOURCE_DRIFT"
        blocker = "PUBLIC_ASSETS_DIFFER_FROM_CANDIDATE"
    else:
        observed = "SOURCE_MATCH_ONLY"
        hold = "HOLD_PROVIDER_RECOVERY_AND_OWNER_EVIDENCE"
        blocker = None
    require(observation["status"] == observed)

    blockers = (["SOURCE_ONLY_NOT_RENDER_DEPLOYMENT",
                 "CURRENT_RENDER_DEPLOY_ID_NOT_INDEPENDENTLY_VERIFIED",
                 "RENDER_ROLLBACK_ARTIFACT_NOT_CONFIRMED",
                 "REAL_ANDROID_ARCHIVE_MIGRATION_NOT_VERIFIED",
                 "SERVICE_SPECIFIC_OWNER_RELEASE_APPROVAL_REQUIRED"])
    if blocker:
        blockers.insert(0, blocker)
    return {
        "schema": DECISION_SCHEMA,
        "source_commit": source_commit,
        "fixed_public_origin": ORIGIN,
        "status": hold,
        "public_source_status": observed,
        "checked_paths": len(FILES),
        "problems": problems,
        "blockers": blockers,
        "source_manifest_and_zip_verified": True,
        "public_origin_read_only_observation": True,
        "render_deploy_identity_confirmed": False,
        "render_rollback_artifact_confirmed": False,
        "production_recovery_tested": False,
        "real_owner_device_verified": False,
        "provider_model_billing_verified": False,
        "owner_release_approval_confirmed": False,
        "deployment_attempted": False,
        "service_configuration_mutated": False,
        "ready_to_promote": False,
        "authority": "none",
    }


def check(zip_path, manifest_path, observation_path, source_commit):
    # Authenticates the exact reviewed source files before interpreting any
    # public observation. Never fetches public URLs itself or reads secrets.
    manifest = gate.verify(zip_path, manifest_path, expected_commit=source_commit)
    observation = load_observation(observation_path)
    return evaluate(manifest=manifest, observation=observation,
                    source_commit=source_commit)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--zip", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--observation", required=True)
    p.add_argument("--source-commit", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    try:
        target = gate.path_is_new_external(args.out)
        result = check(args.zip, args.manifest, args.observation,
                       args.source_commit)
        payload = (json.dumps(result, sort_keys=True, ensure_ascii=True,
                              separators=(",", ":")) + "\n").encode("ascii")
        require(len(payload) < 14000)
        target.write_bytes(payload)
        print(json.dumps({
            "status": result["status"],
            "source_commit": result["source_commit"],
            "public_source_status": result["public_source_status"],
            "problem_count": len(result["problems"]),
            "ready_to_promote": False,
            "authority": "none",
        }, sort_keys=True))
        # A successful safety classification is not production readiness.
        return 0
    except (UntrustedReleaseEvidence, ValueError, TypeError, KeyError,
            OSError, json.JSONDecodeError, RecursionError):
        # No untrusted JSON, paths, provider exception bodies or tokens in logs.
        print("STUDIO RELEASE DECISION: INVALID EVIDENCE; NO RELEASE", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
