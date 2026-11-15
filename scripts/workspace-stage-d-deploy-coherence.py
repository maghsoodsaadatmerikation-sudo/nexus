#!/usr/bin/env python3
"""Read-only, offline deployed-commit coherence check for Railway Stage D.

Takes independently SHA-256 pinned environment inventory, health and two
Railway deployment-history JSON snapshots. A matching deployment is only
metadata consistency, NEVER cryptographic runtime attestation or permission
to wake, restore, rotate keys, migrate disks or deploy.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "nexus_railway_deploy_preflight",
    HERE / "workspace-stage-d-railway-preflight.py")
if spec is None or spec.loader is None:
    raise RuntimeError("Railway Stage D topology preflight unavailable")
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)

SCHEMA = "nexus.stage-d.railway-deployed-commit-coherence.v1"
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
MAX_SNAPSHOT = 256 * 1024
MAX_DEPLOYS = 50


class CoherenceError(Exception):
    pass


def deny(reason):
    raise CoherenceError(reason)


def deployment_history(args, path, sha, service_id, label):
    raw = preflight.exact_snapshot(path, sha, label + " deployment history")
    if set(raw) != {"deployments"}:
        deny(label + " deployment history has unrecognized envelope fields")
    records = preflight.lst(raw["deployments"], label + " deployments")
    if not 1 <= len(records) <= MAX_DEPLOYS:
        deny(label + " deployment history must contain 1-50 records")
    seen = set()
    for record in records:
        preflight.obj(record, label + " deployment")
        identity = preflight.text_value(record.get("id"), label + " deployment id")
        if identity in seen:
            deny(label + " deployment id repeated in filtered history")
        seen.add(identity)
        if (record.get("serviceId") != service_id
                or record.get("environmentId") != args.environment_id):
            deny(label + " history returned an unrelated service or environment")
    return records


def latest_record(records, deployment_id, label):
    matches = [v for v in records if v.get("id") == deployment_id]
    if len(matches) != 1:
        deny(label + " inventory latest deployment is absent from provider history")
    # The provider history is most-recent-first, but the inventory carries
    # an explicit authoritative selection; never substitute another record.
    if records[0]["id"] != deployment_id:
        deny(label + " provider history and inventory disagree on latest deployment")
    return matches[0]


def verify(args):
    if not isinstance(args.expected_commit, str) or not COMMIT.fullmatch(
            args.expected_commit):
        deny("separately approved exact 40-character lowercase commit required")
    if args.source_service_id == args.restore_service_id:
        deny("source and restore must be different service IDs")
    base = preflight.verify(args)
    inventory = preflight.exact_snapshot(
        args.inventory, args.inventory_sha256, "Railway inventory")
    health = preflight.exact_snapshot(
        args.health, args.health_sha256, "Railway health")
    results = {}
    blockers = set(base["blocked_reasons"])
    last_commit = {}
    for role, service_id, path, snapshot_sha in (
            ("source", args.source_service_id, args.source_deployments,
             args.source_deployments_sha256),
            ("recovery", args.restore_service_id, args.restore_deployments,
             args.restore_deployments_sha256)):
        service = preflight.only_named(
            inventory["services"], "id", service_id, "inventory services")
        reported = preflight.only_named(
            health["services"], "serviceId", service_id, "health services")
        latest = preflight.obj(service.get("latestDeployment"),
                               role + " latest deployment")
        identity = preflight.text_value(latest.get("id"),
                                        role + " deployment identity")
        records = deployment_history(
            args, path, snapshot_sha, service_id, role)
        record = latest_record(records, identity, role)
        if record.get("status") != latest.get("status"):
            deny(role + " latest deployment status differs across provider snapshots")
        if not isinstance(record.get("regions"), list):
            deny(role + " deployment regions list missing")
        actual_regions = record["regions"]
        if not actual_regions or any(not isinstance(v, str) for v in actual_regions):
            deny(role + " deployment has no valid recorded region")
        if not set(actual_regions).issubset(set(service["regions"])):
            deny(role + " deployment region disagrees with inventory")
        active = preflight.lst(
            reported.get("activeDeployments"), role + " active deployments")
        if not any(isinstance(v, dict)
                   and v.get("id") == identity
                   and v.get("status") == record["status"] for v in active):
            deny(role + " latest deployment absent from runtime active deployments")
        meta = preflight.obj(record.get("meta"), role + " commit provenance")
        commit = meta.get("commitHash")
        if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
            deny(role + " deployment missing full immutable source commit SHA")
        if meta.get("branch") != "main":
            deny(role + " deployed revision does not claim approved main branch")
        last_commit[role] = commit
        if commit != args.expected_commit:
            blockers.add(role + "_deployed_commit_differs_from_approved_revision")
        if record.get("status") != "SUCCESS":
            blockers.add(role + "_deployment_not_running_successfully")
        results[role] = {
            "service_id": service_id,
            "deployment_id": identity,
            "deployment_status": record["status"],
            "reported_git_commit": commit,
            "reported_branch": "main",
            "history_sha256": snapshot_sha,
            "reported_regions": actual_regions,
        }
    if last_commit["source"] != last_commit["recovery"]:
        blockers.add("source_and_restore_deployed_commits_differ")
    return {
        "schema": SCHEMA,
        "status": "offline-provider-deployment-metadata-reviewed",
        "approved_commit_sha": args.expected_commit,
        "source": results["source"],
        "recovery": results["recovery"],
        "base_preflight": base["online_topology_preflight"],
        "commit_coherence": (
            "SNAPSHOT_CONSISTENT_ONLY" if not blockers else "BLOCKED"),
        "blocked_reasons": sorted(blockers),
        "running_versions_cryptographically_attested": False,
        "provider_snapshots_signed_or_live": False,
        "physical_failure_domain_independence_proven": False,
        "real_offhost_restore_proven": False,
        "production_release_authorized": False,
        "release_gate": "BLOCKED",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("inspect", "release-gate"))
    for name in ("inventory", "health", "source-deployments", "restore-deployments"):
        p.add_argument("--" + name, type=Path, required=True)
        p.add_argument("--" + name + "-sha256", required=True)
    for name in ("project-id", "environment-id", "expected-repo",
                 "source-service-id", "restore-service-id", "source-volume-id",
                 "restore-volume-id", "expected-commit"):
        p.add_argument("--" + name, required=True)
    args = p.parse_args()
    try:
        result = verify(args)
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
        if args.mode == "release-gate":
            print("NEXUS STAGE D DEPLOYMENT COHERENCE RELEASE: BLOCKED", file=sys.stderr)
            return 1
        return 0
    except (CoherenceError, preflight.ProviderError,
            preflight.trust.TrustError, OSError, TypeError, ValueError,
            KeyError) as exc:
        print("NEXUS STAGE D DEPLOYMENT COHERENCE DENIED: " + str(exc),
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
