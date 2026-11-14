#!/usr/bin/env python3
"""Offline, fail-closed read-only review of Render and GitHub release-freeze metadata.

Reads an operator-supplied, SANITIZED pair of provider responses. The result is
never an authorization to merge, deploy, restore, publish evidence or create a Seal.
This tool cannot independently authenticate its input or inspect production data.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import stat
import sys

SCHEMA = "nexus.production-freeze-observation.v1"
MAX_BYTES = 128 * 1024
MAX_AGE = timedelta(minutes=30)
FUTURE_SKEW = timedelta(minutes=2)
REPO = "maghsoodsaadatmerikation-sudo/nexus"
RENDER_SERVICE = "srv-dabhmn0u01pc73b1v1og"
RULESET_ID = 20870033
REQUIRED_CHECK = "readonly-verification"
SHA = re.compile(r"[0-9a-f]{40}\Z")


class InvalidEvidence(ValueError):
    pass


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise InvalidEvidence("duplicate field")
        obj[key] = value
    return obj


def reject_constant(_):
    raise InvalidEvidence("non-finite JSON value")


def read_snapshot(path: Path):
    """Reject aliases and torn files; do not print paths or raw provider fields."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                or not 0 < before.st_size <= MAX_BYTES):
            raise InvalidEvidence("invalid input file")
        chunks = []
        remaining = MAX_BYTES + 1
        while remaining:
            chunk = os.read(fd, min(8192, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(fd)
        if (len(raw) != before.st_size or after.st_nlink != 1
                or (before.st_dev, before.st_ino, before.st_size,
                    before.st_mtime_ns, before.st_ctime_ns) !=
                   (after.st_dev, after.st_ino, after.st_size,
                    after.st_mtime_ns, after.st_ctime_ns)):
            raise InvalidEvidence("input changed or exceeded limit")
    finally:
        os.close(fd)
    return json.loads(raw, object_pairs_hook=unique_object,
                      parse_constant=reject_constant)


def valid_sha(value):
    return type(value) is str and SHA.fullmatch(value) is not None


def checked_utc(value):
    if (type(value) is not str
            or re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value) is None):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def assess(document, expected_main_sha, now=None):
    """Evaluate only metadata consistency, never external truth or authorization."""
    if (type(document) is not dict or set(document) !=
            {"schema", "observed_at_utc", "render", "github_ruleset", "github_main_ref"}
            or document["schema"] != SCHEMA or not valid_sha(expected_main_sha)):
        raise InvalidEvidence("invalid observation envelope")
    now = now or datetime.now(timezone.utc)
    at = checked_utc(document["observed_at_utc"])
    blockers = []
    if at is None or not (now - MAX_AGE <= at <= now + FUTURE_SKEW):
        blockers.append("provider_observation_not_fresh")

    render = document["render"]
    if type(render) is not dict or render.get("id") != RENDER_SERVICE:
        blockers.append("render_service_identity_unverified")
    else:
        if (render.get("repo") != "https://github.com/" + REPO
                or render.get("branch") != "main"
                or render.get("type") != "web_service"
                or not isinstance(render.get("serviceDetails"), dict)
                or render["serviceDetails"].get("env") != "docker"):
            blockers.append("render_source_configuration_mismatch")
        if render.get("autoDeploy") != "no" or render.get("autoDeployTrigger") != "off":
            blockers.append("render_autodeploy_not_disabled")

    main = document["github_main_ref"]
    if (type(main) is not dict or main.get("ref") != "refs/heads/main"
            or not isinstance(main.get("object"), dict)
            or main["object"].get("type") != "commit"
            or main["object"].get("sha") != expected_main_sha):
        blockers.append("github_main_sha_unverified")

    ruleset = document["github_ruleset"]
    if (type(ruleset) is not dict or type(ruleset.get("id")) is not int
            or ruleset["id"] != RULESET_ID or ruleset.get("source") != REPO
            or ruleset.get("target") != "branch"
            or ruleset.get("enforcement") != "active"):
        blockers.append("github_ruleset_identity_unverified")
    else:
        conditions = ruleset.get("conditions")
        ref_name = conditions.get("ref_name") if type(conditions) is dict else None
        if (type(ref_name) is not dict
                or ref_name.get("include") != ["~DEFAULT_BRANCH"]
                or ref_name.get("exclude") != []):
            blockers.append("github_main_not_covered_by_ruleset")
        rule_list = ruleset.get("rules")
        if type(rule_list) is not list or not all(type(r) is dict for r in rule_list):
            blockers.append("github_required_rules_unverified")
        else:
            kinds = [r.get("type") for r in rule_list]
            if (any(kinds.count(x) != 1 for x in
                    ("pull_request", "non_fast_forward", "deletion", "required_status_checks"))):
                blockers.append("github_required_rules_unverified")
            else:
                parameters = next(
                    r["parameters"] for r in rule_list if r["type"] == "required_status_checks"
                ) if all("parameters" in r for r in rule_list if r["type"] == "required_status_checks") else None
                if (type(parameters) is not dict
                        or parameters.get("strict_required_status_checks_policy") is not True
                        or parameters.get("do_not_enforce_on_create") is not False
                        or type(parameters.get("required_status_checks")) is not list
                        or not any(type(c) is dict and c.get("context") == REQUIRED_CHECK
                                   for c in parameters["required_status_checks"])):
                    blockers.append("github_strict_required_checks_missing")
        # An absent/redacted bypass list must never be interpreted as empty.
        if (ruleset.get("bypass_actors") != []
                or ruleset.get("current_user_can_bypass") != "never"):
            blockers.append("github_bypass_scope_unverified")

    return {
        "schema": SCHEMA,
        "configuration_review": "BLOCKED" if blockers else "CONSISTENT_INPUT_ONLY",
        "blockers": blockers,
        "provider_identity_authenticated": False,
        "real_backup_inspected": False,
        "independent_restore_verified": False,
        "merge_authorized": False,
        "deployment_authorized": False,
        "release_seal_authorized": False,
        "authority": "none",
        "claim_boundary": "Operator-supplied metadata only; no provider attestation, backup proof or production release authority.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--expected-main-sha", required=True)
    args = parser.parse_args()
    try:
        report = assess(read_snapshot(args.snapshot), args.expected_main_sha)
    except (InvalidEvidence, OSError, UnicodeError, ValueError, TypeError, OverflowError):
        print("NEXUS FREEZE PREFLIGHT: INVALID OR UNSAFE INPUT", file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if not report["blockers"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
