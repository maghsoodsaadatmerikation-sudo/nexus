#!/usr/bin/env python3
"""Read-only, fail-closed snapshot of NEXUS pull-request merge safeguards.

The output NEVER authorizes merging. It distinguishes green workflow runs from
enforced repository rules and explicitly records owner-review deficiencies.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

REPO = "maghsoodsaadatmerikation-sudo/nexus"
REPO_ID = 1330624116
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
REQUIRED = {
    "NEXUS PR Verification": ".github/workflows/pr-verify.yml",
    "NEXUS v2.6 Request Continuity Verification": ".github/workflows/v2.6-request-continuity.yml",
    "NEXUS Studio Verification": ".github/workflows/studio.yml",
    "NEXUS Static Studio Acceptance": ".github/workflows/studio-static.yml",
    "NEXUS Public Studio Witness": ".github/workflows/studio-static-public.yml",
    "NEXUS v1.8 Historical Signed Evidence Acceptance": ".github/workflows/v18-historical-signed-evidence.yml",
}


class AuditError(ValueError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AuditError(message)


def pairs_unique(pairs: list[tuple[str, object]]) -> dict:
    obj = {}
    for key, value in pairs:
        require(key not in obj, "duplicate JSON key")
        obj[key] = value
    return obj


def read_json(path: Path) -> object:
    require(path.is_file() and not path.is_symlink()
            and path.stat().st_size <= 4 * 1024 * 1024,
            "missing, symlink or oversized metadata")
    try:
        return json.loads(path.read_text(encoding="utf-8"),
                          object_pairs_hook=pairs_unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(AuditError("nonfinite JSON")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AuditError("malformed metadata") from exc


def nested(obj: object, *keys: str) -> object:
    for key in keys:
        if type(obj) is not dict:
            return None
        obj = obj.get(key)
    return obj


def valid_sha(value: object) -> bool:
    return type(value) is str and SHA40.fullmatch(value) is not None


def assess(*, repo: dict, main: dict, pr: dict, ruleset: dict, runs: dict,
           expected_pr: int, expected_sha: str) -> dict:
    require(type(expected_pr) is int and expected_pr > 0, "invalid selected PR")
    require(valid_sha(expected_sha), "invalid pinned head")
    require(all(type(x) is dict for x in (repo, main, pr, ruleset, runs)),
            "metadata response must be JSON object")
    require(repo.get("id") == REPO_ID and type(repo.get("id")) is int
            and repo.get("full_name") == REPO and repo.get("default_branch") == "main"
            and repo.get("archived") is False and repo.get("disabled") is False,
            "repository identity or default branch changed")
    main_sha = nested(main, "commit", "sha")
    require(main.get("name") == "main" and valid_sha(main_sha),
            "invalid main branch response")
    require(pr.get("number") == expected_pr and type(pr.get("number")) is int,
            "wrong PR metadata")
    require(pr.get("state") == "open" and pr.get("merged") is False,
            "PR closed or merged")
    require(nested(pr, "head", "repo", "id") == REPO_ID
            and nested(pr, "base", "repo", "id") == REPO_ID,
            "cross-repository PR or ambiguous fork")
    require(nested(pr, "head", "sha") == expected_sha
            and nested(pr, "base", "sha") == main_sha
            and nested(pr, "base", "ref") == "main",
            "PR head or base is stale, ambiguous or wrong")
    require(pr.get("draft") in (True, False) and type(pr.get("draft")) is bool,
            "draft flag must be boolean")

    require(ruleset.get("id") == 20870033 and type(ruleset.get("id")) is int
            and ruleset.get("enforcement") == "active"
            and ruleset.get("target") == "branch"
            and ruleset.get("source") == REPO,
            "expected active branch ruleset missing/changed")
    require(nested(ruleset, "conditions", "ref_name", "include") == ["~DEFAULT_BRANCH"]
            and nested(ruleset, "conditions", "ref_name", "exclude") == [],
            "branch ruleset no longer targets exactly default branch")
    rules = ruleset.get("rules")
    require(type(rules) is list, "malformed ruleset")
    checks_rule = [x for x in rules if type(x) is dict and x.get("type") == "required_status_checks"]
    pr_rule = [x for x in rules if type(x) is dict and x.get("type") == "pull_request"]
    require(len(checks_rule) == 1 and len(pr_rule) == 1,
            "required status/PR rules missing or duplicate")
    checks_options = checks_rule[0].get("parameters")
    pr_options = pr_rule[0].get("parameters")
    require(type(checks_options) is dict and type(pr_options) is dict,
            "malformed ruleset parameters")
    required_statuses = checks_options.get("required_status_checks")
    require(type(required_statuses) is list
            and any(type(c) is dict and c.get("context") == "readonly-verification"
                    and type(c.get("integration_id")) is int
                    and c["integration_id"] == 15368 for c in required_statuses),
            "readonly-verification status not enforced by expected GitHub app")
    require(type(checks_options.get("strict_required_status_checks_policy")) is bool,
            "strict status check flag absent")
    reviews_required = pr_options.get("required_approving_review_count")
    require(type(reviews_required) is int and reviews_required >= 0,
            "review count unknown")

    workflows = runs.get("workflow_runs")
    require(type(workflows) is list and len(workflows) <= 100,
            "invalid/oversized workflow run page")
    evidence = {}
    for title, path in REQUIRED.items():
        matches = [
            x for x in workflows if type(x) is dict
            and x.get("name") == title and x.get("path") == path
            and x.get("event") == "pull_request"
            and x.get("head_sha") == expected_sha
            and nested(x, "repository", "id") == REPO_ID
            and nested(x, "head_repository", "id") == REPO_ID
            and type(x.get("id")) is int and x["id"] > 0
            and type(x.get("run_attempt")) is int and x["run_attempt"] == 1
            and any(type(p) is dict and p.get("number") == expected_pr
                    for p in x.get("pull_requests", []) if type(x.get("pull_requests")) is list)
        ]
        # Report all matches. A past success doesn't override a later failed
        # attempt for the same exact SHA and PR, and cannot authorize anything.
        latest = max(matches, key=lambda x: x["id"], default=None)
        evidence[title] = {
            "status": "PASS" if latest and latest.get("status") == "completed"
                      and latest.get("conclusion") == "success" else "NOT_PROVEN",
            "run_id": latest["id"] if latest else None,
        }

    blockers = []
    if pr["draft"]:
        blockers.append("DRAFT_PR")
    if pr.get("mergeable") is not True:
        blockers.append("MERGEABILITY_NOT_CONFIRMED")
    if not checks_options["strict_required_status_checks_policy"]:
        blockers.append("STRICT_BASE_FRESHNESS_NOT_ENFORCED")
    if reviews_required == 0:
        blockers.append("INDEPENDENT_APPROVAL_NOT_REQUIRED_BY_RULESET")
    if any(x["status"] != "PASS" for x in evidence.values()):
        blockers.append("EXPECTED_CI_NOT_FULLY_VERIFIED")
    blockers.append("OWNER_REVIEW_AND_EXPLICIT_MERGE_DECISION_REQUIRED")

    return {
        "schema": "nexus.merge-readiness.snapshot.v1",
        "repository": REPO,
        "pr": expected_pr,
        "head_sha": expected_sha,
        "main_sha": main_sha,
        "ruleset_id": ruleset["id"],
        "required_readonly_check_enforced": True,
        "strict_base_freshness_enforced": checks_options["strict_required_status_checks_policy"],
        "required_approvals": reviews_required,
        "workflow_results": evidence,
        "ci_snapshot_green": all(x["status"] == "PASS" for x in evidence.values()),
        "review_state": "HOLD",
        "blockers": blockers,
        "merge_authorized": False,
        "release_authorized": False,
        "production_mutation": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Read-only NEXUS merge readiness report")
    p.add_argument("--repo-json", type=Path, required=True)
    p.add_argument("--main-json", type=Path, required=True)
    p.add_argument("--pr-json", type=Path, required=True)
    p.add_argument("--ruleset-json", type=Path, required=True)
    p.add_argument("--runs-json", type=Path, required=True)
    p.add_argument("--pr-number", type=int, required=True)
    p.add_argument("--head-sha", required=True)
    x = p.parse_args()
    try:
        result = assess(
            repo=read_json(x.repo_json), main=read_json(x.main_json),
            pr=read_json(x.pr_json), ruleset=read_json(x.ruleset_json),
            runs=read_json(x.runs_json), expected_pr=x.pr_number,
            expected_sha=x.head_sha,
        )
    except (AuditError, OSError) as error:
        print(f"NEXUS MERGE AUDIT: INVALID METADATA ({error})", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    print("NEXUS MERGE AUDIT: REVIEW HOLD — NEVER AUTOMATIC MERGE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
