#!/usr/bin/env python3
"""Read-only merge-freshness guard for untrusted NEXUS pull requests.

Success means the observed GitHub ruleset requires strict, current-base checks
AND the PR's evaluated base still equals the live protected-branch tip at
the time of observation. It cannot authorize a deployment or prevent a later
race by itself; strict GitHub branch protection closes that latter window.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

REPOSITORY = "maghsoodsaadatmerikation-sudo/nexus"
RULESET_ID = 20870033
REQUIRED_CHECK = "readonly-verification"
SHA = re.compile(r"[0-9a-f]{40}\Z")
MAX_BYTES = 96 * 1024


class Hold(ValueError):
    pass


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise Hold(reason)


def no_duplicates(pairs: list[tuple[str, object]]) -> dict:
    output = {}
    for key, value in pairs:
        require(key not in output, "duplicate field in GitHub response")
        output[key] = value
    return output


def validate(ruleset: object, branch: object, expected_base_sha: str,
             expected_repo: str = REPOSITORY) -> dict[str, object]:
    require(expected_repo == REPOSITORY, "unexpected repository")
    require(isinstance(expected_base_sha, str)
            and SHA.fullmatch(expected_base_sha) is not None,
            "invalid event base SHA")
    require(type(ruleset) is dict, "invalid GitHub ruleset response")
    require(ruleset.get("id") == RULESET_ID, "wrong ruleset")
    require(ruleset.get("source") == REPOSITORY, "wrong ruleset owner")
    require(ruleset.get("target") == "branch"
            and ruleset.get("enforcement") == "active", "ruleset not active")
    conditions = ruleset.get("conditions")
    require(type(conditions) is dict and type(conditions.get("ref_name")) is dict,
            "no protected branch selector")
    selector = conditions["ref_name"]
    include, exclude = selector.get("include"), selector.get("exclude")
    require(type(include) is list and "~DEFAULT_BRANCH" in include,
            "default branch is not targeted")
    require(type(exclude) is list and not exclude,
            "protected branch has exclusions")
    require(ruleset.get("bypass_actors") == [],
            "ruleset contains bypass actors")
    require(type(branch) is dict and branch.get("ref") == "refs/heads/main",
            "unexpected protected branch ref")
    node = branch.get("object")
    require(type(node) is dict and node.get("type") == "commit",
            "invalid protected branch object")
    live_sha = node.get("sha")
    require(isinstance(live_sha, str) and SHA.fullmatch(live_sha) is not None,
            "invalid live branch SHA")
    require(live_sha == expected_base_sha,
            "PR base is stale relative to current main")
    rules = ruleset.get("rules")
    require(type(rules) is list, "missing ruleset rules")
    by_type: dict[str, list] = {}
    for rule in rules:
        require(type(rule) is dict and isinstance(rule.get("type"), str),
                "invalid ruleset rule")
        by_type.setdefault(rule["type"], []).append(rule)
    require(len(by_type.get("deletion", [])) == 1,
            "protected branch deletion rule missing or duplicated")
    require(len(by_type.get("non_fast_forward", [])) == 1,
            "protected branch force-push guard missing or duplicated")
    require(len(by_type.get("pull_request", [])) == 1,
            "protected branch PR rule missing or duplicated")
    status_rules = by_type.get("required_status_checks", [])
    require(len(status_rules) == 1, "required status check rule missing or duplicated")
    params = status_rules[0].get("parameters")
    require(type(params) is dict, "invalid status-check parameters")
    require(params.get("strict_required_status_checks_policy") is True,
            "required checks are not strict/up-to-date with main")
    required = params.get("required_status_checks")
    require(type(required) is list and bool(required),
            "no required status checks")
    matching = [
        check for check in required
        if type(check) is dict and check.get("context") == REQUIRED_CHECK
        and type(check.get("integration_id")) is int
        and check.get("integration_id") > 0
    ]
    require(len(matching) == 1,
            "trusted GitHub Actions verification check missing or ambiguous")
    return {
        "status": "PASS",
        "observed_main_sha": live_sha,
        "pr_base_sha": expected_base_sha,
        "ruleset_id": RULESET_ID,
        "strict_status_checks": True,
        "required_check": REQUIRED_CHECK,
        "production_release_authorized": False,
    }


def fetch_json_via_gh(path: str) -> object:
    # Paths are hardcoded below. Never read user-provided URL or credentials.
    try:
        process = subprocess.run(
            ["gh", "api", "--method", "GET", path],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
            timeout=15, env=os.environ.copy(),
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Hold("GitHub read-only observation unavailable") from error
    require(process.returncode == 0 and 0 < len(process.stdout) <= MAX_BYTES,
            "GitHub read-only observation failed or exceeded size bound")
    try:
        return json.loads(process.stdout.decode("utf-8"),
                          object_pairs_hook=no_duplicates)
    except (ValueError, UnicodeError) as error:
        raise Hold("invalid GitHub JSON response") from error


def main() -> int:
    try:
        require(os.getenv("GITHUB_EVENT_NAME") == "pull_request",
                "not a pull-request verification context")
        require(os.getenv("GITHUB_REPOSITORY") == REPOSITORY,
                "unexpected GitHub repository context")
        require(os.getenv("NEXUS_PR_BASE_REF") == "main",
                "PR does not target protected main")
        expected = os.getenv("NEXUS_PR_BASE_SHA", "")
        require(SHA.fullmatch(expected) is not None,
                "missing exact PR event base SHA")
        ruleset = fetch_json_via_gh(
            f"repos/{REPOSITORY}/rulesets/{RULESET_ID}"
        )
        branch = fetch_json_via_gh(
            f"repos/{REPOSITORY}/git/ref/heads/main"
        )
        report = validate(ruleset, branch, expected)
        print(json.dumps(report, sort_keys=True))
        print("PR BASE AND RULESET FRESHNESS: PASS")
        return 0
    except Hold as error:
        print(f"PR BASE AND RULESET FRESHNESS: BLOCKED ({error})",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
