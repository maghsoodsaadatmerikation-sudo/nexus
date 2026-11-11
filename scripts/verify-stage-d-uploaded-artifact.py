#!/usr/bin/env python3
"""Verify that GitHub returned the exact ciphertext artifact uploaded by Stage D.

This is an independent runner *transport-byte* check, not a real backup,
private-key proof, origin attestation, point-in-time snapshot or live restore.
No Railway credentials, private keys, or plaintext are used.
"""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "nexus_stage_d_retrieval_anchor", HERE / "stage-d-run-log-anchor.py")
anchor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(anchor)

SCHEMA = "nexus.stage-d-uploaded-ciphertext-retrieval.v1"
EXPECTED_FILES = {anchor.CIPHERTEXT, anchor.RECEIPT}
BASE64 = re.compile(r"[A-Za-z0-9+/]+={0,2}\Z")


class RetrievalBlocked(ValueError):
    pass


def require(condition):
    if not condition:
        raise RetrievalBlocked("uploaded ciphertext was not independently retrieved and matched")


def exact_artifact_directory(directory):
    require(directory.is_absolute() and directory.is_dir() and
            not directory.is_symlink() and
            directory == directory.resolve(strict=True))
    names = set()
    for path in directory.iterdir():
        info = path.lstat()
        require(path.name in EXPECTED_FILES and
                stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
        names.add(path.name)
    require(names == EXPECTED_FILES)


def decode_anchor(encoded):
    require(type(encoded) is str and 0 < len(encoded) <= 8192 and
            len(encoded) % 4 == 0 and BASE64.fullmatch(encoded) is not None)
    try:
        raw = base64.b64decode(encoded, validate=True)
        require(base64.b64encode(raw).decode("ascii") == encoded)
        line = raw.decode("utf-8", "strict")
    except (ValueError, UnicodeError):
        raise RetrievalBlocked("invalid non-secret anchor transfer") from None
    require(0 < len(line) <= anchor.MAX_ANCHOR + 1)
    require(line.startswith(anchor.PREFIX) and
            (line.count("\n") == 0 or (line.count("\n") == 1 and line.endswith("\n"))))
    return line


def verify_retrieval(directory, encoded_anchor, run_id, attempt, sha, artifact_id):
    require(type(sha) is str and anchor.SHA.fullmatch(sha) is not None)
    require(type(artifact_id) is str)
    artifact_number = anchor.positive_int(artifact_id)
    run = anchor.positive_int(run_id)
    run_attempt = anchor.positive_int(attempt)
    exact_artifact_directory(directory)
    line = decode_anchor(encoded_anchor)
    old = anchor.verify(directory, line, run, run_attempt, sha)
    require(old["status"] == "LOG_ANCHOR_LOCAL_FILE_MATCH_ONLY" and
            old["seal"] is False and old["authority"] == "none")
    exact_artifact_directory(directory)
    return {
        "schema": SCHEMA,
        "status": "INDEPENDENT_RUNNER_CIPHERTEXT_BYTES_MATCH",
        "run_id": run,
        "run_attempt": run_attempt,
        "commit_sha": sha,
        "artifact_id": artifact_number,
        "file_count": len(EXPECTED_FILES),
        "artifact_readback": "same_workflow_fresh_runner",
        "ciphertext_decrypted": False,
        "owner_offsite_custody": "not_verified",
        "railway_provider_origin": "not_independently_attested",
        "source_atomicity": "not_verified",
        "independent_production_backup": False,
        "release_authorized": False,
        "seal": False,
        "authority": "none",
    }


def main():
    # Metadata is supplied via GitHub job-to-job outputs and runner context,
    # never from a PR author or production credential.
    env = os.environ
    try:
        require(all(not env.get(name) for name in (
            "RAILWAY_TOKEN", "RAILWAY_API_TOKEN", "NEXUS_API_TOKEN",
            "RENDER_API_KEY", "NEXUS_STAGE_D_RAILWAY_TOKEN",
            "NEXUS_STAGE_D_RAILWAY_WORKSPACE_API_TOKEN")))
        require(env.get("GITHUB_ACTIONS") == "true" and
                env.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and
                env.get("GITHUB_REF") == "refs/heads/main" and
                env.get("GITHUB_REPOSITORY") == anchor.REPO and
                env.get("GITHUB_WORKFLOW_REF") == anchor.WORKFLOW_REF)
        require(env.get("GITHUB_SHA") == env.get("EXPECTED_SHA"))
        result = verify_retrieval(
            Path(env["RETRIEVED_ARTIFACT_DIR"]),
            env["TRANSFER_ANCHOR_B64"],
            env["GITHUB_RUN_ID"],
            env["GITHUB_RUN_ATTEMPT"],
            env["GITHUB_SHA"],
            env["TRANSFER_ARTIFACT_ID"])
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (ValueError, OSError, TypeError, KeyError, UnicodeError):
        # Intentionally no private paths, content, provider output or tokens.
        print("STAGE D ENCRYPTED ARTIFACT RE-DOWNLOAD: BLOCKED (no backup or Seal claim)",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
