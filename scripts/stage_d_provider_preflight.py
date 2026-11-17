#!/usr/bin/env python3
"""Offline Stage D Railway metadata preflight. Never grants release authority.

Input is a small, explicitly provided provider-metadata observation, NOT an
independent public HTTP witness. This tool never contacts a network, reads
volume files, or authorizes deployments, paid operations, or release Seals.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
import sys

SCHEMA = "nexus.stage-d.provider-readonly-snapshot.v1"
REPORT = "nexus.stage-d.release-metadata-triage.v1"
MAX_BYTES = 8192
FIELDS = frozenset((
    "schema", "observed_date", "provider", "service", "environment",
    "github_main_at_observation", "historical_v17_gate_target",
    "railway_live_source", "railway_deployment_status",
    "live_healthcheck_path", "staged_healthcheck_path",
    "staged_change_count", "sleep_application_enabled",
    "durable_mount_path", "runtime_identity_observed",
    "independent_volume_restore_observed",
    "provider_metadata_only",
))
SHA_PATTERN = re.compile(r"[0-9a-f]{40}")


class InvalidSnapshot(ValueError):
    pass


def require(condition: bool, label: str) -> None:
    if not condition:
        raise InvalidSnapshot(label)


def unique_keys(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        require(key not in result, "duplicate-field")
        result[key] = value
    return result


def reject_constant(_: str) -> None:
    raise InvalidSnapshot("non-finite-json")


def require_sha(value: object) -> None:
    require(type(value) is str and SHA_PATTERN.fullmatch(value) is not None,
            "invalid-source-identity")


def triage(document: object) -> dict:
    require(type(document) is dict and frozenset(document) == FIELDS,
            "invalid-field-set")
    require(document["schema"] == SCHEMA, "invalid-schema")
    require(document["provider"] == "Railway" and
            document["service"] == "nexus-stage-d" and
            document["environment"] == "production",
            "unsupported-runtime-identity")
    observed = document["observed_date"]
    require(type(observed) is str and
            re.fullmatch(r"\d{4}-\d{2}-\d{2}", observed) is not None,
            "invalid-observation-date")
    try:
        parsed = date.fromisoformat(observed)
    except ValueError as exc:
        raise InvalidSnapshot("invalid-observation-date") from exc
    require(date(2026, 1, 1) <= parsed <= datetime.now(timezone.utc).date(),
            "invalid-observation-date")

    for key in ("github_main_at_observation",
                "historical_v17_gate_target", "railway_live_source"):
        require_sha(document[key])
    require(document["railway_deployment_status"] in
            ("SUCCESS", "FAILED", "CRASHED", "SLEEPING", "UNKNOWN"),
            "invalid-deployment-status")
    for key in ("live_healthcheck_path", "staged_healthcheck_path"):
        require(type(document[key]) is str and
                document[key] in ("/", "/readyz", "/livez", "none"),
                "invalid-healthcheck-path")
    changes = document["staged_change_count"]
    require(type(changes) is int and 0 <= changes <= 100,
            "invalid-staged-change-count")
    for key in ("sleep_application_enabled", "runtime_identity_observed",
                "independent_volume_restore_observed", "provider_metadata_only"):
        require(type(document[key]) is bool, "invalid-claim-boolean")
    require(document["durable_mount_path"] in ("/data", "none"),
            "invalid-mount-path")

    # A provider metadata envelope can NEVER claim independent live or restore
    # evidence. Reject attempts to smuggle such "yes" claims into the input.
    require(document["provider_metadata_only"] is True,
            "not-a-provider-metadata-snapshot")
    require(document["runtime_identity_observed"] is False,
            "runtime-attestation-must-use-independent-protocol")
    require(document["independent_volume_restore_observed"] is False,
            "restoration-attestation-must-use-independent-protocol")

    main = document["github_main_at_observation"]
    live = document["railway_live_source"]
    historical = document["historical_v17_gate_target"]
    drift_main = main != live
    drift_historical = historical != live
    staged = changes != 0 or document["staged_healthcheck_path"] != "none"
    healthcheck_change = (document["staged_healthcheck_path"] != "none" and
                          document["staged_healthcheck_path"] !=
                          document["live_healthcheck_path"])

    # This is deliberately only a diagnosis, not a readiness check: any
    # input document could be fabricated or become stale immediately.
    return {
        "schema": REPORT,
        "status": "HOLD_INDEPENDENT_RUNTIME_AND_RECOVERY_EVIDENCE",
        "snapshot_date": observed,
        "source_conflicts": {
            "repo_main_vs_reported_railway": drift_main,
            "historical_v17_target_vs_reported_railway": drift_historical,
            "repo_main_vs_historical_v17_target": main != historical,
        },
        "staged_config_present": staged,
        "staged_healthcheck_change": healthcheck_change,
        "reported_sleep_application": document["sleep_application_enabled"],
        "reported_deployment_success": document["railway_deployment_status"] == "SUCCESS",
        "reported_volume_mounted": document["durable_mount_path"] == "/data",
        "provider_metadata_only": True,
        "live_http_identity_independently_verified": False,
        "on_device_android_verified": False,
        "recovery_independently_verified": False,
        "current_main_at_runtime_checked": False,
        "release_authorized": False,
        "seal_granted": False,
        "paid_mutation_authorized": False,
        "production_mutation": False,
        "authority": "none",
    }


def parse(raw: bytes) -> dict:
    require(0 < len(raw) <= MAX_BYTES, "invalid-snapshot-size")
    try:
        data = json.loads(raw.decode("utf-8", errors="strict"),
                          object_pairs_hook=unique_keys,
                          parse_constant=reject_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise InvalidSnapshot("invalid-json") from exc
    return triage(data)


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("snapshot", type=Path)
    args = cli.parse_args(argv)
    try:
        require(args.snapshot.is_file() and
                not args.snapshot.is_symlink() and
                args.snapshot.stat().st_size <= MAX_BYTES,
                "invalid-snapshot-file")
        report = parse(args.snapshot.read_bytes())
    except (InvalidSnapshot, OSError, TypeError):
        # Do not echo paths, unexpected values, provider IDs or contents.
        print(json.dumps({"schema": REPORT, "status": "INVALID_OR_UNTRUSTED_SNAPSHOT",
                          "release_authorized": False, "authority": "none"}))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
