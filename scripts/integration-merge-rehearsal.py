#!/usr/bin/env python3
"""Read-only exact-ref dry-run merges. Never touches a production ref or provider.

In GitHub Actions, fetch the listed Git refs in a disposable checkout first.
This script invokes git merge-tree only, emits path-only sanitized metadata, and
returns 0 when it successfully classified both mergeable and blocked candidates.
Exit 0 is NOT release approval; status in the receipt owns the actual meaning.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SHA = re.compile(r"[0-9a-f]{40}\Z")
CANDIDATES = {
    "storage-base-129": "refs/remotes/origin/rehearsal-129",
    "cumulative-work-mode-134": "refs/remotes/origin/rehearsal-134",
    "cloud-admission-153": "refs/remotes/origin/rehearsal-153",
    "cloud-operations-155": "refs/remotes/origin/rehearsal-155",
    "public-observer-157": "refs/remotes/origin/rehearsal-157",
}
MAX_BYTES = 256 * 1024
MAX_CONFLICTS = 128


def git(*args: str, timeout: int = 50) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, check=False, timeout=timeout)


def clean_sha(ref: str) -> str:
    result = git("rev-parse", "--verify", ref + "^{commit}", timeout=12)
    sha = result.stdout.decode("ascii", "replace").strip()
    if result.returncode != 0 or not SHA.fullmatch(sha):
        raise ValueError("missing-or-invalid-ref")
    return sha


def parse_merge_tree(data: bytes, code: int) -> dict:
    if code not in (0, 1) or not data or len(data) > MAX_BYTES:
        raise ValueError("merge-tree-did-not-return-bounded-data")
    fields = data.split(b"\0")
    tree = fields[0].decode("ascii", "replace").strip()
    if not SHA.fullmatch(tree):
        raise ValueError("merge-tree-invalid-result")
    if code == 0:
        # Git emits only the tree SHA for clean mergers in --name-only mode.
        if any(part for part in fields[1:]):
            raise ValueError("unexpected-clean-merge-output")
        return {"status": "CLEAN_MERGE_REHEARSAL_ONLY", "conflict_paths": [],
                "result_tree_sha": tree}

    # After the tree ID: conflicting filenames, blank NUL, then diagnostic
    # records. Never display diagnostic content or source bytes to the user.
    try:
        sep = fields.index(b"", 1)
    except ValueError as exc:
        raise ValueError("malformed-merge-conflicts") from exc
    names = fields[1:sep]
    if not names or len(names) > MAX_CONFLICTS:
        raise ValueError("unbounded-merge-conflicts")
    safe_names = []
    for raw in names:
        if len(raw) > 256 or not raw or b"\n" in raw or b"\r" in raw or b"\t" in raw:
            raise ValueError("unsafe-conflict-path")
        path = raw.decode("utf-8", "strict")
        pieces = Path(path).parts
        if path.startswith("/") or ".." in pieces or not pieces:
            raise ValueError("unsafe-conflict-path")
        safe_names.append(path)
    return {"status": "BLOCKED_BY_MERGE_CONFLICT", "conflict_paths": safe_names,
            "result_tree_sha": None}


def inspect(base: str, candidates: dict[str, str]) -> dict:
    target = clean_sha(base)
    outputs = []
    for name, ref in candidates.items():
        candidate = clean_sha(ref)
        result = git("merge-tree", "--write-tree", "--name-only", "-z",
                     target, candidate)
        result_record = parse_merge_tree(result.stdout, result.returncode)
        outputs.append({
            "candidate": name, "head_sha": candidate, "base_sha": target,
            **result_record,
        })
    return {
        "schema": "nexus.integration.merge-rehearsal.v1",
        "authority": "none",
        "status": "REHEARSAL_COMPLETE_PRODUCTION_BLOCKED",
        "baseline": target,
        "candidates": outputs,
        "merge_executed": False,
        "production_deployed": False,
        "durable_restore_proven": False,
        "render_autodeploy_safe": False,
        "release_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="refs/remotes/origin/main")
    parser.add_argument("--output", type=Path, default=Path("integration-rehearsal.json"))
    args = parser.parse_args()
    try:
        report = inspect(args.base, CANDIDATES)
        content = json.dumps(report, indent=2, sort_keys=True) + "\n"
        # Preserve existing evidence; a repeated invocation should not overwrite
        # a potentially different observation.
        args.output.write_text(content, encoding="utf-8")
        print("MERGE REHEARSAL: CLASSIFIED (no production authorization)")
        for item in report["candidates"]:
            print(f'{item["candidate"]}: {item["status"]}, conflicts={len(item["conflict_paths"])}')
        return 0
    except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired):
        print("MERGE REHEARSAL: BLOCKED (unable to verify exact refs)", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
