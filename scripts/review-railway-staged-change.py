#!/usr/bin/env python3
"""Fail-closed, non-mutating inspection of one known Railway staged patch.

No Railway credentials, network calls, or production actions. An exact diff
match means *eligible for human review*, not approved for deployment.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import stat
from pathlib import Path

SCHEMA = "nexus.railway-staged-patch-capture.v1"
RESULT_SCHEMA = "nexus.railway-staged-patch-review.v1"
MAX_BYTES = 96 * 1024
PROJECT = "2ac7887b-d67a-48be-8a7b-bd54092893ae"
ENVIRONMENT = "56c4bc45-0e62-4aa9-832f-884bb1aa620c"
SERVICE = "0032fc74-2c52-475d-b9df-9dca59237d93"
PATCH = "5439a0d6-3921-4746-8545-29313d3d7437"
PATH_PREFIX = "services." + SERVICE + ".deploy."
EXPECTED = {
    PATH_PREFIX + "healthcheckPath": {"displayName": "Healthcheck Path", "type": "updated", "from": "/", "to": "/readyz", "destructive": False},
    PATH_PREFIX + "sleepApplication": {"displayName": "Sleep Application", "type": "updated", "from": "true", "to": "true", "destructive": False},
}


class InvalidCapture(Exception):
    pass


def object_no_duplicates(pairs):
    value = {}
    for name, content in pairs:
        if name in value:
            raise InvalidCapture("duplicate_json_key")
        value[name] = content
    return value


def load(path: Path):
    """Reject links and nonregular files, read a bounded fd, not a pathname twice."""
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise InvalidCapture("input_cannot_be_opened") from exc
    try:
        mode = os.fstat(fd)
        if not stat.S_ISREG(mode.st_mode) or mode.st_nlink != 1:
            raise InvalidCapture("input_not_single_link_regular_file")
        if mode.st_mode & 0o077:
            raise InvalidCapture("input_permissions_too_open")
        if mode.st_size > MAX_BYTES:
            raise InvalidCapture("input_too_large")
        with os.fdopen(fd, "rb", closefd=False) as f:
            data = f.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise InvalidCapture("input_too_large")
    except OSError as exc:
        raise InvalidCapture("input_cannot_be_read") from exc
    finally:
        os.close(fd)
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=object_no_duplicates,
                           parse_constant=lambda _: (_ for _ in ()).throw(InvalidCapture("nonfinite_json")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise InvalidCapture("invalid_json") from exc
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise InvalidCapture("wrong_capture_schema")
    return value


def parse_utc(value):
    if not isinstance(value, str):
        return None
    try:
        when = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        return None
    return when.astimezone(dt.timezone.utc)


def inspect(document: dict, *, now=None):
    """Only allowlisted fields appear in the result; never emit raw provider data."""
    now = now or dt.datetime.now(dt.timezone.utc)
    blockers = []
    alerts = []

    def demand(condition, reason):
        if not condition:
            blockers.append(reason)

    captured = parse_utc(document.get("captured_at_utc"))
    capture_fresh = captured is not None and -60 <= (now - captured).total_seconds() <= 900
    demand(capture_fresh, "capture_not_recent")
    view = document.get("staged_changes")
    if not isinstance(view, dict):
        raise InvalidCapture("staged_changes_missing")
    project, environment, stage = (view.get(k) for k in ("project", "environment", "staged"))
    if not all(isinstance(item, dict) for item in (project, environment, stage)):
        raise InvalidCapture("provider_identity_or_staged_missing")
    demand(project.get("id") == PROJECT, "project_mismatch")
    demand(environment.get("id") == ENVIRONMENT and environment.get("name") == "production", "environment_mismatch")
    demand(stage.get("patchId") == PATCH, "patch_identity_mismatch")
    demand(stage.get("status") == "STAGED", "patch_not_staged")
    demand(type(stage.get("changeCount")) is int and stage.get("changeCount") == 2, "patch_change_count_not_two")
    updated = parse_utc(stage.get("updatedAt"))
    demand(updated is not None, "patch_update_time_missing")
    if updated is not None:
        demand(updated <= now + dt.timedelta(minutes=1), "patch_updated_in_future")
        if now - updated > dt.timedelta(hours=72):
            alerts.append("patch_unchanged_for_over_72_hours")
    demand(view.get("destructive") is False, "patch_marked_destructive")
    demand(view.get("sharedVariables") == [], "shared_variables_changed_or_unknown")
    demand("privateNetworkDisabled" in view and view["privateNetworkDisabled"] is None,
           "private_network_change_or_unknown")
    resources = view.get("resources")
    demand(isinstance(resources, list) and len(resources) == 1, "unexpected_resource_count")
    if isinstance(resources, list) and len(resources) == 1 and isinstance(resources[0], dict):
        resource = resources[0]
        demand(resource.get("kind") == "service" and resource.get("id") == SERVICE and resource.get("name") == "nexus-stage-d" and resource.get("action") == "update", "unexpected_resource_identity_or_action")
        changes = resource.get("changes")
        if not isinstance(changes, list) or len(changes) != 2:
            demand(False, "unexpected_changed_field_count")
        else:
            paths = []
            for change in changes:
                if not isinstance(change, dict) or not isinstance(change.get("path"), str):
                    demand(False, "malformed_changed_field")
                    continue
                path = change["path"]
                paths.append(path)
                wanted = EXPECTED.get(path)
                demand(wanted is not None and {k: change.get(k) for k in wanted} == wanted
                       and set(change) == set(wanted) | {"path"}, "unexpected_field_change")
            demand(set(paths) == set(EXPECTED) and len(paths) == len(set(paths)), "expected_changes_missing_or_repeated")
    else:
        demand(False, "resource_entry_invalid")
    return {
        "schema": RESULT_SCHEMA,
        "exact_diff_review": "MATCH" if not blockers else "BLOCKED",
        "blockers": sorted(set(blockers)),
        "alerts": sorted(set(alerts)),
        "target_service_id": SERVICE,
        "expected_patch_id": PATCH,
        "change_summary": "healthcheck / -> /readyz; sleepApplication true -> true",
        "next_action": "HUMAN_REVIEW_REQUIRED" if not blockers else "STOP_AND_REINSPECT",
        "live_change_applied": False,
        "deployment_authorized": False,
        "production_mutation": False,
        "authority_expansion": "NONE",
        "scope": "Exact known staged diff only; not a health check, source pin check, backup, restore, or approval. A_out <= A_in.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = inspect(load(args.input))
    except (InvalidCapture, AttributeError, TypeError, ValueError) as exc:
        reason = str(exc) if isinstance(exc, InvalidCapture) else "invalid_provider_shape"
        result = {"schema": RESULT_SCHEMA, "exact_diff_review": "BLOCKED", "blockers": [reason],
                  "next_action": "STOP_AND_REINSPECT", "live_change_applied": False,
                  "deployment_authorized": False, "production_mutation": False,
                  "authority_expansion": "NONE"}
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result["exact_diff_review"] == "MATCH" else 2


if __name__ == "__main__":
    raise SystemExit(main())
