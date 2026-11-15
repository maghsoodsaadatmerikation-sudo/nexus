#!/usr/bin/env python3
"""Read-only Railway Stage D provider snapshot review; release always blocked.

Provider inventory and health are UNTRUSTED, independently SHA-256 pinned
snapshots. This tool DOES NOT call Railway, wake sleeping services, read
credentials, trigger deploys, inspect disk content or certify independence.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "nexus_provider_snapshot_trust", HERE / "workspace-trust.py")
if spec is None or spec.loader is None:
    raise RuntimeError("strict NEXUS trust codec unavailable")
trust = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trust)

SCHEMA = "nexus.stage-d.railway-provider-preflight.v1"
MAX_BYTES = 1024 * 1024


class ProviderError(Exception):
    pass


def deny(reason):
    raise ProviderError(reason)


def obj(value, label):
    if not isinstance(value, dict):
        deny(label + " must be a JSON object")
    return value


def lst(value, label):
    if not isinstance(value, list):
        deny(label + " must be a JSON array")
    return value


def text_value(value, label):
    if not isinstance(value, str) or not value or len(value) > 512:
        deny(label + " must be a nonempty bounded string")
    return value


def exact_snapshot(path, expected_sha, label):
    if not path.is_absolute():
        deny(label + " must use an explicitly selected absolute path")
    if not isinstance(expected_sha, str) or not trust.SHA256_HEX.fullmatch(expected_sha):
        deny("independently retained " + label + " SHA-256 pin is required")
    raw = trust.open_no_symlinks(path, MAX_BYTES)
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        deny(label + " changed against independently retained exact file bytes")
    return obj(trust.strict_json(raw), label)


def only_named(items, key, identifier, label):
    found = [item for item in lst(items, label)
             if isinstance(item, dict) and item.get(key) == identifier]
    if len(found) != 1:
        deny(label + " must have exactly one matching independently approved identifier")
    return found[0]


def mapped_volumes(service, inventory, expected_volume, label):
    expected = text_value(expected_volume, label + " expected volume")
    mounts = lst(service.get("volumeMounts"), label + " volumeMounts")
    found = [item for item in mounts
             if isinstance(item, dict) and item.get("volumeId") == expected]
    if len(found) != 1:
        deny(label + " expected mounted volume missing or ambiguous")
    mount = found[0]
    if mount.get("mountPath") != "/data":
        deny(label + " expected private durable /data mount absent")
    entry = only_named(inventory.get("volumes"), "id", expected, "inventory volumes")
    if obj(entry.get("mountedOn"), label + " mount metadata").get("serviceId") != service["id"]:
        deny(label + " volume is assigned to another service")
    if entry.get("state") != "live" or entry.get("region") not in lst(
            service.get("regions"), label + " regions"):
        deny(label + " volume does not match a live region-local service mount")
    return {"volume_id": expected, "region": entry["region"]}


def verify(args):
    inventory = exact_snapshot(
        args.inventory, args.inventory_sha256, "Railway inventory")
    health = exact_snapshot(args.health, args.health_sha256, "Railway health")
    inv_project = obj(inventory.get("project"), "inventory project")
    inv_env = obj(inventory.get("environment"), "inventory environment")
    health_env = obj(health.get("environment"), "health environment")
    project_id = text_value(args.project_id, "approved project")
    environment_id = text_value(args.environment_id, "approved environment")
    if (inv_project.get("id") != project_id
            or inv_env.get("id") != environment_id
            or health_env.get("id") != environment_id):
        deny("provider snapshots refer to a different approved project/environment")
    if health_env.get("name") != inv_env.get("name"):
        deny("provider snapshots disagree on environment name")

    origin_id = text_value(args.source_service_id, "approved source service")
    restore_id = text_value(args.restore_service_id, "approved restore service")
    origin_volume = text_value(args.source_volume_id, "approved source volume")
    restore_volume = text_value(args.restore_volume_id, "approved restore volume")
    if origin_id == restore_id or origin_volume == restore_volume:
        deny("source and recovery must not share service or mounted volume IDs")
    expected_repo = text_value(args.expected_repo, "approved repository")
    services = inventory.get("services")
    origin = only_named(services, "id", origin_id, "inventory services")
    restore = only_named(services, "id", restore_id, "inventory services")
    summaries = {}
    blockers = []
    for role, service, ident, volume_id in (
            ("source", origin, origin_id, origin_volume),
            ("recovery", restore, restore_id, restore_volume)):
        actual_source = obj(service.get("source"), role + " source")
        if actual_source.get("repo") != expected_repo:
            deny(role + " service source differs from approved repository")
        if service.get("id") != ident or not isinstance(service.get("name"), str):
            deny(role + " service identity metadata malformed")
        volume = mapped_volumes(service, inventory, volume_id, role)
        status = only_named(health.get("services"), "serviceId", ident, "health services")
        if status.get("serviceName") != service["name"]:
            deny(role + " provider inventory and runtime identity disagree")
        service_state = service.get("state")
        health_state = status.get("state")
        if not isinstance(service_state, str) or not isinstance(health_state, str):
            deny(role + " states must be named explicitly")
        configured = service_state == "live"
        running = health_state == "online"
        active = lst(status.get("activeDeployments"), role + " active deployments")
        deployment = obj(service.get("latestDeployment"), role + " latest deployment")
        deployment_id = text_value(deployment.get("id"), role + " latest deployment id")
        status_matches = (
            len(active) == 1
            and isinstance(active[0], dict)
            and active[0].get("id") == deployment_id
            and active[0].get("status") == "SUCCESS"
            and deployment.get("status") == "SUCCESS")
        replicas = status.get("replicaStatus")
        replicas_ready = (
            isinstance(replicas, dict)
            and type(replicas.get("running")) is int
            and replicas["running"] >= 1
            and type(replicas.get("total")) is int
            and replicas["total"] >= replicas["running"]
            and type(replicas.get("crashed")) is int
            and replicas["crashed"] == 0)
        if not configured:
            blockers.append(role + "_service_not_unstaged_live")
        if not running:
            blockers.append(role + "_service_not_online")
        if not status_matches:
            blockers.append(role + "_deployment_not_verified_running_success")
        if not replicas_ready:
            blockers.append(role + "_running_replica_not_verified")
        summaries[role] = {
            "service_id": ident,
            "service_name": service["name"],
            "service_state": service_state,
            "health_state": health_state,
            "volume_id": volume["volume_id"],
            "region": volume["region"],
            "latest_deployment_status": deployment.get("status"),
            "running_replica_verified": replicas_ready,
        }

    if summaries["source"]["region"] == summaries["recovery"]["region"]:
        blockers.append("source_and_restore_same_reported_region")
    staged = inventory.get("staged")
    pending = lst(health.get("pendingWork"), "health pending work")
    if staged is not None or pending:
        blockers.append("unapplied_or_applying_environment_patch")
    # Railway returns a global summary that may report no issues while
    # inactive services are SLEEPING: never rely on summary.hasIssues alone.
    result = {
        "schema": SCHEMA,
        "status": "provider-snapshot-inspected",
        "inventory_sha256": args.inventory_sha256,
        "health_sha256": args.health_sha256,
        "project_id": project_id,
        "environment_id": environment_id,
        "source": summaries["source"],
        "recovery": summaries["recovery"],
        "different_reported_regions": (
            summaries["source"]["region"] != summaries["recovery"]["region"]),
        "different_reported_service_and_volume_ids": True,
        "blocked_reasons": sorted(set(blockers)),
        "online_topology_preflight": "BLOCKED" if blockers else "SNAPSHOT_CONSISTENT_ONLY",
        "provider_signed_snapshots_verified": False,
        "independent_failure_domains_proven": False,
        "real_offhost_restore_proven": False,
        "current_deployed_commit_verified": False,
        "production_release_authorized": False,
        "release_gate": "BLOCKED",
    }
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("inspect", "release-gate"))
    for flag in ("inventory", "health"):
        p.add_argument("--" + flag, required=True, type=Path)
        p.add_argument("--" + flag + "-sha256", required=True)
    for flag in ("project-id", "environment-id", "expected-repo",
                 "source-service-id", "restore-service-id",
                 "source-volume-id", "restore-volume-id"):
        p.add_argument("--" + flag, required=True)
    args = p.parse_args()
    try:
        result = verify(args)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        if args.mode == "release-gate":
            print("NEXUS RAILWAY REAL-HOST GATE: BLOCKED; snapshot topology is not two-host proof", file=sys.stderr)
            return 1
        return 0
    except (ProviderError, trust.TrustError, OSError, ValueError, TypeError, KeyError) as exc:
        print("NEXUS RAILWAY SNAPSHOT DENIED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
