#!/usr/bin/env python3
"""Read-only, fail-closed Railway cutover preflight. Never authorizes promotion."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import stat
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA = "nexus.railway-cutover-input.v1"
OUT_SCHEMA = "nexus.railway-cutover-assessment.v1"
MAX_BYTES = 256 * 1024
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
REQUIRED_ENV = frozenset({"NEXUS_API_TOKEN", "NEXUS_DATA_DIR", "NEXUS_BIND_ADDR", "PORT"})
PUBLIC_PATHS = {
    "/v1/runtime-identity": 200,
    "/livez": 200,
    "/readyz": 200,
    "/v1/workspaces": 401,
    "/v1/requests/nexus-public-observation": 401,
}


class InvalidInput(Exception):
    pass


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise InvalidInput("duplicate_json_key")
        obj[key] = value
    return obj


def read_snapshot(path):
    # Inspect and read one descriptor, not a repeatedly resolved pathname.
    # Nonblocking open also prevents a FIFO from stalling preflight.
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise InvalidInput("missing_or_linked_input") from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise InvalidInput("missing_or_linked_input")
        if info.st_size > MAX_BYTES:
            raise InvalidInput("input_too_large")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise InvalidInput("input_too_large")
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                           parse_constant=lambda _: (_ for _ in ()).throw(InvalidInput("nonfinite_number")))
    except (UnicodeError, json.JSONDecodeError, OSError, RecursionError) as exc:
        raise InvalidInput("invalid_json") from exc
    finally:
        os.close(fd)
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise InvalidInput("unexpected_schema")
    return value


def fresh(value, now, minutes=30):
    if not isinstance(value, str):
        return False
    try:
        instant = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    if instant.tzinfo is None:
        return False
    seconds = (now - instant).total_seconds()
    return -60 <= seconds <= minutes * 60


def assessment(data, *, project_id, service_id, volume_id, expected_commit,
               expected_digest, expected_origin, always_on=False, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    blocked = []

    def require(condition, code):
        if not condition:
            blocked.append(code)

    inventory = data.get("inventory")
    service = data.get("service")
    health = data.get("health")
    deployments = data.get("deployments")
    public = data.get("public_observation")
    if not all(isinstance(x, dict) for x in (inventory, service, health, deployments, public)):
        raise InvalidInput("missing_provider_or_public_sections")

    require(fresh(data.get("captured_at_utc"), now), "snapshot_not_fresh")
    require(inventory.get("project", {}).get("id") == project_id, "inventory_project_mismatch")
    require("staged" in inventory and inventory["staged"] is None,
            "environment_has_pending_or_unknown_changes")
    env = inventory.get("environment")
    env = env if isinstance(env, dict) else {}
    environment_id = env.get("id")
    require(env.get("name") == "production", "not_production_environment")
    require(isinstance(environment_id, str) and bool(environment_id), "environment_identity_missing")
    require(service.get("environment", {}).get("id") == environment_id
            and health.get("environment", {}).get("id") == environment_id,
            "cross_environment_evidence_mismatch")
    require(service.get("service", {}).get("id") == service_id, "service_identity_mismatch")
    require(service.get("service", {}).get("state") == "live", "service_not_unchanged_live")
    require("staged" in service and service["staged"] is None
            and service.get("stagedChanges") == [], "service_has_pending_or_unknown_changes")

    config = service.get("config") if isinstance(service.get("config"), dict) else {}
    source = config.get("source") if isinstance(config.get("source"), dict) else {}
    require(source.get("repo") == "maghsoodsaadatmerikation-sudo/nexus", "source_repository_mismatch")
    require(source.get("branch") == "main", "source_branch_mismatch")
    require(source.get("commitSha") == expected_commit, "source_commit_not_pinned_to_candidate")
    deploy = config.get("deploy") if isinstance(config.get("deploy"), dict) else {}
    require(deploy.get("healthcheckPath") == "/readyz", "healthcheck_not_readyz")
    if always_on:
        require(deploy.get("sleepApplication") is False, "service_sleep_enabled")

    mounted = service.get("volumes")
    require(isinstance(mounted, list) and any(
        isinstance(v, dict) and v.get("id") == volume_id
        and v.get("mountPath") == "/data" and v.get("state") == "live" for v in mounted
    ), "expected_persistent_mount_missing")
    vars_ = service.get("variableNames")
    require(isinstance(vars_, list) and REQUIRED_ENV.issubset(set(v for v in vars_ if isinstance(v, str))),
            "required_environment_variable_names_missing")
    net = service.get("domains") if isinstance(service.get("domains"), dict) else {}
    domains = net.get("serviceDomains")
    host = urlsplit(expected_origin).hostname
    require(isinstance(domains, list) and any(
        isinstance(d, dict) and d.get("domain") == host and d.get("targetPort") == 3000 for d in domains
    ), "public_domain_not_bound")

    statuses = health.get("services")
    matched = [s for s in statuses if isinstance(s, dict) and s.get("serviceId") == service_id] if isinstance(statuses, list) else []
    require(len(matched) == 1, "health_service_missing_or_ambiguous")
    active_id = None
    if len(matched) == 1:
        entry = matched[0]
        require(entry.get("state") == "online", "service_not_online")
        active = entry.get("activeDeployments")
        if isinstance(active, list) and len(active) >= 1 and isinstance(active[0], dict):
            active_id = active[0].get("id")
            require(active[0].get("status") == "SUCCESS", "active_deployment_not_success")
        else:
            require(False, "active_deployment_missing")
        require(entry.get("issues", {}).get("criticalCount") == 0
                and entry.get("recentFailures") == 0, "runtime_has_recent_failures")
    dep_list = deployments.get("deployments")
    found = [d for d in dep_list if isinstance(d, dict) and d.get("id") == active_id] if isinstance(dep_list, list) and active_id else []
    require(len(found) == 1, "deployment_metadata_missing")
    if len(found) == 1:
        record = found[0]
        require(record.get("serviceId") == service_id and record.get("status") == "SUCCESS",
                "deployment_not_success")
        require(record.get("environmentId") == environment_id,
                "deployment_environment_mismatch")
        meta = record.get("meta") if isinstance(record.get("meta"), dict) else {}
        require(meta.get("commitHash") == expected_commit, "deployed_commit_differs_from_candidate")

    require(public.get("schema") == "nexus.pilot.public-observation.v1", "public_observation_wrong_schema")
    require(fresh(public.get("observed_at_utc"), now), "public_observation_not_fresh")
    require(public.get("origin") == expected_origin, "public_origin_mismatch")
    require(public.get("expected_source_tree_sha256") == expected_digest
            and public.get("observed_source_tree_sha256") == expected_digest
            and public.get("candidate_digest_match") is True,
            "public_runtime_digest_mismatch")
    observations = public.get("observations")
    for path, status in PUBLIC_PATHS.items():
        check = observations.get(path) if isinstance(observations, dict) else None
        require(isinstance(check, dict) and check.get("method") == "GET"
                and check.get("http_status") == status and not check.get("error"),
                "public_get_boundary_failed:" + path)
    require(public.get("public_checks") == "SATISFIED" and public.get("blockers") == [],
            "public_observer_not_satisfied")
    require(public.get("promotion_ready") is False and public.get("production_mutation") is False,
            "public_observer_claims_unearned_authority")
    require(health.get("pendingWork") == [], "provider_has_pending_or_unknown_work")

    return {
        "schema": OUT_SCHEMA,
        "technical_preflight": "SATISFIED" if not blocked else "BLOCKED",
        "blockers": sorted(set(blocked)),
        "candidate_commit": expected_commit,
        "public_origin": expected_origin,
        "service_profile": "always_on" if always_on else "on_demand",
        "independent_offsite_backup": "NOT_ASSESSED",
        "restore_rehearsal": "NOT_ASSESSED",
        "production_release_authorized": False,
        "provider_mutation": False,
        "authority_expansion": "NONE",
        "claim_boundary": "A read-only, operator-supplied snapshot and public GET preflight; not proof of external custody, signed runtime identity, backup recovery, release approval or future uptime.",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--expected-project-id", required=True)
    p.add_argument("--expected-service-id", required=True)
    p.add_argument("--expected-volume-id", required=True)
    p.add_argument("--expected-commit", required=True)
    p.add_argument("--expected-digest", required=True)
    p.add_argument("--expected-origin", required=True)
    p.add_argument("--always-on", action="store_true")
    args = p.parse_args()
    parsed = urlsplit(args.expected_origin)
    if (not SHA40.fullmatch(args.expected_commit) or not SHA64.fullmatch(args.expected_digest)
            or parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment or parsed.port is not None):
        p.error("candidate SHA, source digest, and HTTPS origin must be exact and credential-free")
    try:
        value = assessment(read_snapshot(args.input), project_id=args.expected_project_id,
                           service_id=args.expected_service_id, volume_id=args.expected_volume_id,
                           expected_commit=args.expected_commit, expected_digest=args.expected_digest,
                           expected_origin=args.expected_origin, always_on=args.always_on)
    except (InvalidInput, AttributeError, TypeError, ValueError) as exc:
        # Never echo raw input or provider messages.
        value = {"schema": OUT_SCHEMA, "technical_preflight": "BLOCKED",
                 "blockers": [str(exc) if isinstance(exc, InvalidInput) else "invalid_snapshot_shape"],
                 "production_release_authorized": False, "provider_mutation": False,
                 "authority_expansion": "NONE"}
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0 if value["technical_preflight"] == "SATISFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
