#!/usr/bin/env python3
"""Source-only Stage D public identity comparator. NO networking or host changes.

The only real-server probe is in the separate manually opted-in workflow.
A matching public endpoint value remains non-authoritative build metadata,
not proof of a release, a running candidate's Git SHA, or durable recovery.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

SCHEMA = "nexus.stage-d.manual-runtime-observation.v1"
INPUTS = ("Cargo.toml", "Cargo.lock", "Dockerfile", "src", "artifact-05",
          "web", "scripts/source-tree-digest.sh")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
MAX_RESPONSE_BYTES = 4096
MAX_TREE_FILES = 30000


class Rejected(ValueError):
    pass


def require(value: bool, label: str) -> None:
    if not value:
        raise Rejected(label)


def source_tree_digest(root: Path) -> str:
    """Reproduce scripts/source-tree-digest.sh (find, sorted sha256sum lines).

    Never runs code from the candidate checkout. Restrict to regular files and
    never follow symlinks. Reject unsafe source paths instead of guessing.
    """
    require(root.is_dir() and not root.is_symlink(), "invalid-candidate-root")
    for item in INPUTS:
        expected = root / item
        require(expected.exists() and not expected.is_symlink(),
                "missing-or-linked-candidate-source")
    paths = []
    for item in INPUTS:
        target = root / item
        if target.is_file():
            paths.append(item)
            continue
        for parent, dirs, files in os.walk(target, followlinks=False):
            dirs[:] = [d for d in dirs if d != "target" and
                       not (Path(parent) / d).is_symlink()]
            for name in files:
                p = Path(parent) / name
                require(not p.is_symlink(), "candidate-symlink-not-supported")
                require(p.is_file(), "nonregular-source-file")
                paths.append(p.relative_to(root).as_posix())
                require(len(paths) <= MAX_TREE_FILES, "too-many-source-files")
    require(paths and len(paths) <= MAX_TREE_FILES, "missing-source-files")
    digest = hashlib.sha256()
    for item in sorted(paths, key=lambda p: os.fsencode(p)):
        file = root / item
        require(not file.is_symlink(), "candidate-file-symlink")
        mode = file.stat().st_mode
        require(stat.S_ISREG(mode), "candidate-nonregular-file")
        # sha256sum emits two spaces between digest and pathname.
        filehash = hashlib.sha256(file.read_bytes()).hexdigest()
        digest.update((filehash + "  " + item + "\n").encode("utf-8"))
    return digest.hexdigest()


def no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate-public-json-key")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise Rejected("invalid-public-json-number")


def public_identity(data: bytes) -> str | None:
    if not (0 < len(data) <= MAX_RESPONSE_BYTES):
        return None
    try:
        parsed = json.loads(data.decode("utf-8", errors="strict"),
                            object_pairs_hook=no_duplicate_keys,
                            parse_constant=reject_constant)
    except (ValueError, UnicodeError, TypeError):
        return None
    if not isinstance(parsed, dict) or set(parsed) != {
        "schema", "source_tree_sha256", "authority"
    }:
        return None
    if (parsed["schema"] != "nexus.runtime-identity.v1" or
        parsed["authority"] != "non_authoritative_build_metadata" or
        type(parsed["source_tree_sha256"]) is not str or
        HEX64.fullmatch(parsed["source_tree_sha256"]) is None):
        return None
    return parsed["source_tree_sha256"]


def assess(*, expected_digest: str, public_body: bytes,
           http_status: str, transport_exit: int, deployed_source_sha: str,
           observer_main_sha: str, reported_source_snapshot_sha: str) -> dict:
    for value in (deployed_source_sha, observer_main_sha,
                  reported_source_snapshot_sha):
        require(type(value) is str and HEX40.fullmatch(value) is not None,
                "invalid-sha-input")
    require(type(expected_digest) is str and HEX64.fullmatch(expected_digest) is not None,
            "invalid-reference-digest")
    require(type(http_status) is str and re.fullmatch(r"\d{3}\Z", http_status),
            "invalid-http-status")
    require(type(transport_exit) is int and 0 <= transport_exit <= 255,
            "invalid-curl-exit-code")
    observed = public_identity(public_body)
    matched = (transport_exit == 0 and http_status == "200" and
               observed is not None and observed == expected_digest)
    return {
        "schema": SCHEMA,
        "status": ("HTTP_METADATA_MATCH_ONLY" if matched else
                   "HTTP_IDENTITY_MISSING_INVALID_OR_DRIFT"),
        "observer_main_sha": observer_main_sha,
        "operator_reported_deployed_source_sha": deployed_source_sha,
        "dated_provider_snapshot_source_sha": reported_source_snapshot_sha,
        "operator_source_matches_dated_provider_snapshot": (
            deployed_source_sha == reported_source_snapshot_sha
        ),
        "observer_main_matches_operator_source": (
            observer_main_sha == deployed_source_sha
        ),
        "expected_reviewed_source_tree_sha256": expected_digest,
        "observed_public_source_tree_sha256": observed,
        "http_status": http_status,
        "transport_succeeded": transport_exit == 0,
        "valid_public_runtime_identity": observed is not None,
        "exact_digest_match": matched,
        "public_http_get_only": True,
        "no_redirects_or_auth_headers_requested": True,
        "this_is_self_reported_build_metadata": True,
        "actual_deployment_sha_cryptographically_proven": False,
        "independent_runtime_execution_verified": False,
        "private_storage_or_restore_verified": False,
        "production_release_authorized": False,
        "production_mutation": False,
        "seal_granted": False,
        "authority": "none",
    }


def safe_file_read(file: Path, max_size: int) -> bytes:
    require(file.is_file() and not file.is_symlink(), "invalid-response-file")
    require(file.stat().st_size <= max_size, "oversize-response")
    return file.read_bytes()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidate-root", required=True, type=Path)
    ap.add_argument("--response-file", type=Path, required=True)
    ap.add_argument("--http-status", required=True)
    ap.add_argument("--curl-exit", type=int, required=True)
    ap.add_argument("--deployed-source-sha", required=True)
    ap.add_argument("--main-sha", required=True)
    ap.add_argument("--snapshot-source-sha", required=True)
    ap.add_argument("--report", required=True, type=Path)
    args = ap.parse_args(argv)
    try:
        digest = source_tree_digest(args.candidate_root)
        body = safe_file_read(args.response_file, MAX_RESPONSE_BYTES)
        result = assess(
            expected_digest=digest, public_body=body,
            http_status=args.http_status, transport_exit=args.curl_exit,
            deployed_source_sha=args.deployed_source_sha,
            observer_main_sha=args.main_sha,
            reported_source_snapshot_sha=args.snapshot_source_sha,
        )
        require(not args.report.exists() and not args.report.is_symlink(),
                "report-already-exists")
        args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
        print(result["status"])
        return 0 if result["status"] == "HTTP_METADATA_MATCH_ONLY" else 1
    except (Rejected, OSError, ValueError):
        # Never print raw public body, private paths, user input, or credentials.
        print("INVALID_PUBLIC_RUNTIME_WITNESS (NO RELEASE AUTHORITY)",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
