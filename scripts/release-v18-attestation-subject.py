#!/usr/bin/env python3
"""Second boundary: inspect successful gh-attestation-verify JSON and actual artifact.

This is NOT a signature verifier. The caller MUST run GitHub CLI's cryptographic
verification with exact signer/source constraints and check its zero exit status,
then hand its untouched JSON output to this offline consistency gate. Do not
consume results from an untrusted file without that prior CLI operation.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import sys

import importlib.util

BASE = Path(__file__).with_name("release-run-provenance.py")
SPEC = importlib.util.spec_from_file_location("nexus_release_source", BASE)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("source verifier not available")
source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)

ProvenanceError = source.ProvenanceError
require = source.require
read_json = source.read_json
nested = source.nested

def read_attestation_results(path: Path) -> list[dict]:
    # The gh CLI can return a JSON array; source.read_json intentionally accepts
    # only objects, so read and validate the top-level array separately.
    import json
    require(path.is_file() and not path.is_symlink()
            and path.stat().st_size <= 2 * 1024 * 1024, "missing/oversized verification result")
    try:
        entries = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=source.canonical_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ProvenanceError("non-finite verification JSON")),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ProvenanceError("invalid verification JSON") from exc
    require(type(entries) is list and 1 <= len(entries) <= 30,
            "expected bounded nonempty verified attestation array")
    require(all(type(e) is dict for e in entries), "invalid result entry")
    return entries


def verify_verified_output(*, result: list[dict], evidence: bytes,
                           expected_repo_id: int) -> dict[str, object]:
    require(type(evidence) is bytes and 0 < len(evidence) <= 1024 * 1024,
            "invalid or oversized evidence content")
    require(type(expected_repo_id) is int and expected_repo_id > 0,
            "invalid expected repository ID")
    require(type(result) is list and 1 <= len(result) <= 30,
            "invalid attestation results")
    digest = hashlib.sha256(evidence).hexdigest()
    for entry in result:
        require(type(entry) is dict, "non-object verification entry")
        vr = entry.get("verificationResult")
        require(type(vr) is dict, "missing verificationResult")
        cert = nested(vr, "signature", "certificate")
        require(type(cert) is dict, "missing trusted certificate")
        # GitHub documents this as the stable, immutable repository ID.
        require(str(cert.get("sourceRepositoryIdentifier")) == str(expected_repo_id)
                and type(cert.get("sourceRepositoryIdentifier")) in (str, int),
                "attested repository ID does not match live repository")
        statement = vr.get("statement")
        require(type(statement) is dict, "missing verified statement")
        require(statement.get("predicateType") == "https://slsa.dev/provenance/v1",
                "unexpected signed predicate type")
        subjects = statement.get("subject")
        require(type(subjects) is list and len(subjects) == 1
                and type(subjects[0]) is dict, "must have one unambiguous subject")
        hash_value = nested(subjects[0], "digest", "sha256")
        require(type(hash_value) is str and re.fullmatch(r"[0-9a-f]{64}", hash_value) is not None,
                "missing exact SHA-256 subject")
        require(hash_value == digest, "signed subject SHA-256 differs from actual evidence bytes")
        timestamps = vr.get("verifiedTimestamps")
        require(type(timestamps) is list, "missing verified timestamp field")
    return {
        "status": "ATTESTATION_RESULT_CONSISTENT_ONLY",
        "subject_sha256": digest,
        "verified_result_count": len(result),
        "repository_id": expected_repo_id,
        "release_authorized": False,
        "production_mutation": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="NEXUS v1.8 attestation subject audit (no signature verification)")
    p.add_argument("--verified-json", type=Path, required=True,
                   help="JSON from successful gh attestation verify --format json (not arbitrary input)")
    p.add_argument("--artifact", type=Path, required=True)
    p.add_argument("--repo-id", type=int, required=True)
    args = p.parse_args()
    try:
        require(args.artifact.is_file() and not args.artifact.is_symlink()
                and args.artifact.stat().st_size <= 1024 * 1024,
                "missing/oversized/symlink artifact")
        report = verify_verified_output(
            result=read_attestation_results(args.verified_json),
            evidence=args.artifact.read_bytes(),
            expected_repo_id=args.repo_id,
        )
    except (ProvenanceError, OSError) as exc:
        print(f"ATTESTATION SUBJECT AUDIT: DENIED ({exc})", file=sys.stderr)
        return 1
    print("ATTESTATION SUBJECT AUDIT: CONSISTENT ONLY (no release authority)")
    print("Validated subject SHA-256: " + str(report["subject_sha256"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
