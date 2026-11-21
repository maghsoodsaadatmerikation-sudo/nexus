#!/usr/bin/env python3
"""Read-only, fail-closed identity gate for NEXUS workflow_run release events.

GitHub API JSON is supplied by the privileged workflow, not downloaded by
this module. This module never grants release authority or calls GitHub.
Run it from a trusted, pinned main checkout *before* checking out any candidate
or running any candidate-controlled command, and repeat just before publication.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

SHA = re.compile(r"[0-9a-f]{40}\Z")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
SOURCE_WORKFLOWS = {
    "v1.6": ("NEXUS Verification", ".github/workflows/verify.yml"),
    "v1.7": ("NEXUS Verification", ".github/workflows/verify.yml"),
    "v1.8": ("NEXUS v1.8 Independent Rebuild", ".github/workflows/v1.8-independent-rebuild.yml"),
    "v1.9": ("NEXUS Verification", ".github/workflows/verify.yml"),
    "v2.0": ("NEXUS v2.0 Capability Verification", ".github/workflows/v2.0-capability.yml"),
    "v2.1": ("NEXUS v2.1 Enforcement Verification", ".github/workflows/v2.1-enforcement.yml"),
    "v2.2": ("NEXUS v2.2 Revocation Replay Verification", ".github/workflows/v2.2-revocation.yml"),
    "v2.3": ("NEXUS v2.3 Revocation Freshness Verification", ".github/workflows/v2.3-revocation-freshness.yml"),
    "v2.4": ("NEXUS v2.4 Gateway Authority-Confusion Verification", ".github/workflows/v2.4-gateway-authority-confusion.yml"),
    "v2.5": ("NEXUS v2.5 Unified Transport Authentication Verification", ".github/workflows/v2.5-transport-authentication.yml"),
}


class ProvenanceError(ValueError):
    pass


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ProvenanceError(reason)


def canonical_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON property")
        result[key] = value
    return result


def read_json(path: Path) -> dict:
    require(path.is_file() and path.stat().st_size <= 2 * 1024 * 1024, "missing or oversized metadata")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=canonical_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ProvenanceError("non-finite JSON")))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ProvenanceError("invalid JSON") from error
    require(type(value) is dict, "metadata must be an object")
    return value


def nested(value: dict, *keys: str):
    for key in keys:
        if type(value) is not dict or key not in value:
            return None
        value = value[key]
    return value


def validate(*, release: str, repo: str, run_id: int, sha: str, workflow_sha: str,
             run: dict, repository: dict, main_branch: dict) -> None:
    require(release in SOURCE_WORKFLOWS, "unknown release gate")
    require(type(repo) is str and REPO.fullmatch(repo) is not None, "invalid repository selector")
    require(type(run_id) is int and run_id > 0, "invalid source run ID")
    require(type(sha) is str and SHA.fullmatch(sha) is not None, "invalid candidate SHA")
    require(type(workflow_sha) is str and SHA.fullmatch(workflow_sha) is not None, "invalid trusted workflow SHA")
    require(type(run) is dict and type(repository) is dict and type(main_branch) is dict,
            "metadata objects required")

    expected_name, expected_path = SOURCE_WORKFLOWS[release]
    repo_id = repository.get("id")
    require(type(repo_id) is int and repo_id > 0, "invalid repository ID")
    require(repository.get("full_name") == repo and repository.get("default_branch") == "main",
            "unexpected repository identity/default branch")
    require(repository.get("archived") is False and repository.get("disabled") is False,
            "archived/disabled repository or incomplete metadata")
    require(main_branch.get("name") == "main", "wrong main branch response")
    main_sha = nested(main_branch, "commit", "sha")
    require(type(main_sha) is str and SHA.fullmatch(main_sha) is not None,
            "invalid main branch SHA")
    require(sha == main_sha == workflow_sha, "candidate is not pinned to current trusted main")

    require(type(run.get("id")) is int and run["id"] == run_id, "source run ID mismatch")
    require(run.get("name") == expected_name and run.get("path") == expected_path,
            "wrong workflow name/path")
    require(run.get("event") == "push" and run.get("head_branch") == "main",
            "source must be an actual push on main, not a PR, dispatch or scheduled run")
    require(run.get("status") == "completed" and run.get("conclusion") == "success",
            "source run not successfully completed")
    require(type(run.get("run_attempt")) is int and run["run_attempt"] == 1,
            "rerun/unknown attempt cannot authorize publication")
    require(run.get("head_sha") == sha, "source run head SHA differs from candidate")
    require(nested(run, "repository", "id") == repo_id
            and nested(run, "repository", "full_name") == repo,
            "source run repository does not match verified repository")
    require(nested(run, "head_repository", "id") == repo_id
            and nested(run, "head_repository", "full_name") == repo,
            "fork or ambiguous head repository")
    head_commit = nested(run, "head_commit", "id")
    if head_commit is not None:
        require(head_commit == sha, "source head commit mismatch")


def main() -> int:
    p = argparse.ArgumentParser(description="NEXUS release provenance gate (read-only)")
    p.add_argument("--release", required=True, choices=sorted(SOURCE_WORKFLOWS))
    p.add_argument("--repo", required=True)
    p.add_argument("--run-id", required=True, type=int)
    p.add_argument("--sha", required=True)
    p.add_argument("--workflow-sha", required=True)
    p.add_argument("--run-json", required=True, type=Path)
    p.add_argument("--repo-json", required=True, type=Path)
    p.add_argument("--main-json", required=True, type=Path)
    args = p.parse_args()
    try:
        validate(release=args.release, repo=args.repo, run_id=args.run_id,
                 sha=args.sha, workflow_sha=args.workflow_sha,
                 run=read_json(args.run_json), repository=read_json(args.repo_json),
                 main_branch=read_json(args.main_json))
    except (ProvenanceError, OSError) as exc:
        print(f"RELEASE SOURCE PROVENANCE: DENIED ({exc})", file=sys.stderr)
        return 1
    print("RELEASE SOURCE PROVENANCE: PASS (metadata only; no release authority)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
