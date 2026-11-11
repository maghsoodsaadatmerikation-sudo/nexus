#!/usr/bin/env python3
"""Bound encrypted escrow to a GitHub workflow RUN LOG without paid attestations.

emit: print a single non-secret, versioned digest anchor to GitHub job logs,
      after encryption but before encrypted-artifact upload.
verify: compare a separately obtained authentic run-log line to downloaded
        ciphertext/receipt. The caller MUST separately verify the log's
        identity and completed-success state in GitHub; this script makes NO
        GitHub network calls, is NOT a signature and grants NO authority.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

PREFIX = "NEXUS_ENCRYPTED_ESCROW_ANCHOR_V1 "
REPO = "maghsoodsaadatmerikation-sudo/nexus"
WORKFLOW_PATH = ".github/workflows/stage-d-encrypted-volume-capture.yml"
WORKFLOW_REF = REPO + "/" + WORKFLOW_PATH + "@refs/heads/main"
VOLUME = "cc47a350-6c7e-4487-89d9-c4b390f94884"
SHA = re.compile(r"[0-9a-f]{40}\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
SCHEMA = "nexus.stage-d-encrypted-log-anchor.v1"
CIPHERTEXT = "nexus-stage-d-private-capture.cms"
RECEIPT = "nexus-stage-d-ciphertext-receipt.json"
MAX_CIPHER = 65 * 1024 * 1024
MAX_JSON = 32768
MAX_ANCHOR = 4096
ANCHOR_KEYS = {
    "schema", "status", "repository", "workflow_ref", "ref", "event",
    "run_id", "run_attempt", "commit_sha", "original_volume_id",
    "ciphertext_sha256", "ciphertext_bytes", "receipt_sha256",
    "recipient_cert_sha256", "provider_origin", "release_authorized", "authority",
}

spec = importlib.util.spec_from_file_location(
    "stage_d_run_anchor_snapshot", Path(__file__).with_name("data-snapshot.py"))
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)
spec = importlib.util.spec_from_file_location(
    "stage_d_run_anchor_escrow", Path(__file__).with_name("stage-d-encrypted-escrow.py"))
escrow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(escrow)


class AnchorBlocked(ValueError):
    pass


def require(condition):
    if not condition:
        raise AnchorBlocked("missing, drifted, unauthenticated or unexpected log anchor")


def strict_json(data):
    return json.loads(data, object_pairs_hook=snapshot.unique_object)


def canonical_read(path, limit):
    require(path.is_absolute() and path.parent.is_dir() and
            path.parent == path.parent.resolve() and not path.is_symlink())
    return snapshot.read_regular(path, limit)


def read_cipher_receipt(directory):
    require(directory.is_absolute() and directory.is_dir() and
            directory == directory.resolve() and not directory.is_symlink())
    cipher_file = directory / CIPHERTEXT
    receipt_file = directory / RECEIPT
    cipher_bytes = canonical_read(cipher_file, MAX_CIPHER)
    receipt_bytes = canonical_read(receipt_file, MAX_JSON)
    content = strict_json(receipt_bytes)
    require(type(content) is dict)
    fixed = {
        "schema": "nexus.stage-d-encrypted-escrow.v1",
        "status": "ENCRYPTED_PRIVATE_COPY_NOT_ATOMICALLY_VERIFIED",
        "content_claim": "local_structural_intake_only",
        "independent_live_restore": "not_evaluated",
        "railway_origin": "not_independently_attested",
        "release_authorized": False,
        "seal": False,
        "authority": "none",
        "recipient_cert_sha256": escrow.CERT_SHA256,
        "ciphertext_sha256": hashlib.sha256(cipher_bytes).hexdigest(),
        "ciphertext_bytes": len(cipher_bytes),
    }
    require(set(content) == set(fixed))
    for key, value in fixed.items():
        require(type(content[key]) is type(value) and content[key] == value)
    return cipher_bytes, receipt_bytes, content


def positive_int(value):
    require(type(value) is str and
            bool(re.fullmatch(r"[1-9][0-9]{0,18}", value)))
    return int(value)


def make_anchor(directory, environ):
    cipher_bytes, receipt_bytes, meta = read_cipher_receipt(directory)
    require(environ.get("GITHUB_ACTIONS") == "true" and
            environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and
            environ.get("GITHUB_REF") == "refs/heads/main" and
            environ.get("GITHUB_REPOSITORY") == REPO and
            environ.get("GITHUB_WORKFLOW_REF") == WORKFLOW_REF)
    sha = environ.get("GITHUB_SHA", "")
    require(type(sha) is str and SHA.fullmatch(sha) is not None)
    anchor = {
        "schema": SCHEMA,
        "status": "CIPHERTEXT_LOCAL_DIGEST_BEFORE_UPLOAD",
        "repository": REPO,
        "workflow_ref": WORKFLOW_REF,
        "ref": "refs/heads/main",
        "event": "workflow_dispatch",
        "run_id": positive_int(environ.get("GITHUB_RUN_ID")),
        "run_attempt": positive_int(environ.get("GITHUB_RUN_ATTEMPT")),
        "commit_sha": sha,
        "original_volume_id": VOLUME,
        "ciphertext_sha256": meta["ciphertext_sha256"],
        "ciphertext_bytes": meta["ciphertext_bytes"],
        "receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
        "recipient_cert_sha256": escrow.CERT_SHA256,
        "provider_origin": "not_independently_attested",
        "release_authorized": False,
        "authority": "none",
    }
    # No secret or workspace path from the process environment is included.
    require(set(anchor) == ANCHOR_KEYS)
    # Guard against replacement after local inspection but before log emission.
    require(canonical_read(directory / CIPHERTEXT, MAX_CIPHER) == cipher_bytes and
            canonical_read(directory / RECEIPT, MAX_JSON) == receipt_bytes)
    return anchor


def validate_anchor(anchor, expected_run_id, expected_attempt, expected_sha):
    require(type(anchor) is dict and set(anchor) == ANCHOR_KEYS)
    exact = {
        "schema": SCHEMA,
        "status": "CIPHERTEXT_LOCAL_DIGEST_BEFORE_UPLOAD",
        "repository": REPO,
        "workflow_ref": WORKFLOW_REF,
        "ref": "refs/heads/main",
        "event": "workflow_dispatch",
        "run_id": expected_run_id,
        "run_attempt": expected_attempt,
        "commit_sha": expected_sha,
        "original_volume_id": VOLUME,
        "recipient_cert_sha256": escrow.CERT_SHA256,
        "provider_origin": "not_independently_attested",
        "release_authorized": False,
        "authority": "none",
    }
    for key, value in exact.items():
        require(type(anchor[key]) is type(value) and anchor[key] == value)
    require(type(anchor["ciphertext_sha256"]) is str and
            HEX.fullmatch(anchor["ciphertext_sha256"]) is not None)
    require(type(anchor["receipt_sha256"]) is str and
            HEX.fullmatch(anchor["receipt_sha256"]) is not None)
    require(type(anchor["ciphertext_bytes"]) is int and
            256 < anchor["ciphertext_bytes"] <= MAX_CIPHER)


def verify(directory, log_line, expected_run_id, expected_attempt, expected_sha):
    require(type(log_line) is str and len(log_line) <= MAX_ANCHOR and
            log_line.startswith(PREFIX) and log_line.count("\n") <= 1)
    encoded = log_line[len(PREFIX):].strip("\r\n")
    anchor = strict_json(encoded)
    validate_anchor(anchor, expected_run_id, expected_attempt, expected_sha)
    cipher_bytes, receipt_bytes, meta = read_cipher_receipt(directory)
    require(anchor["ciphertext_sha256"] == meta["ciphertext_sha256"] and
            anchor["ciphertext_bytes"] == meta["ciphertext_bytes"] and
            anchor["receipt_sha256"] == hashlib.sha256(receipt_bytes).hexdigest())
    # Repeat the complete content observation before declaring equality.
    require(canonical_read(directory / CIPHERTEXT, MAX_CIPHER) == cipher_bytes and
            canonical_read(directory / RECEIPT, MAX_JSON) == receipt_bytes)
    return {
        "schema": SCHEMA,
        "status": "LOG_ANCHOR_LOCAL_FILE_MATCH_ONLY",
        "github_job_success": "not_independently_checked",
        "authentic_log_origin": "operator_must_check_in_github",
        "railway_provider_origin": "not_independently_attested",
        "atomic_source_consistency": "not_verified",
        "production_recovery": "not_evaluated",
        "seal": False,
        "authority": "none",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    cmd = parser.add_subparsers(dest="operation", required=True)
    emit_parser = cmd.add_parser("emit")
    emit_parser.add_argument("--encrypted-dir", type=Path, required=True)
    verify_parser = cmd.add_parser("verify")
    verify_parser.add_argument("--encrypted-dir", type=Path, required=True)
    verify_parser.add_argument("--anchor-file", type=Path, required=True)
    verify_parser.add_argument("--expected-run-id", required=True)
    verify_parser.add_argument("--expected-attempt", required=True)
    verify_parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args()
    try:
        if args.operation == "emit":
            anchor = make_anchor(args.encrypted_dir, os.environ)
            print(PREFIX + json.dumps(anchor, sort_keys=True, separators=(",", ":")))
        else:
            require(type(args.expected_sha) is str and
                    SHA.fullmatch(args.expected_sha) is not None)
            anchor_line = canonical_read(args.anchor_file, MAX_ANCHOR).decode("utf-8")
            report = verify(args.encrypted_dir, anchor_line,
                            positive_int(args.expected_run_id),
                            positive_int(args.expected_attempt),
                            args.expected_sha)
            print(json.dumps(report, sort_keys=True))
        return 0
    except (ValueError, OSError, TypeError, UnicodeError):
        # Never print the actual log line, workspace, account environment,
        # ciphertext, or any private filesystem path to stderr on failure.
        print("ENCRYPTED RUN LOG ANCHOR: BLOCKED (not a provenance proof)",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
