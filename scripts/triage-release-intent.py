#!/usr/bin/env python3
"""Offline, fail-closed triage of NON-RELEASE GitHub release-gate refusals.

This reads only an explicitly supplied, sanitized metadata fixture. It never
calls GitHub, Railway or a production endpoint; never releases, authorizes,
retries or changes a Git ref. Its exit zero means only that all seven observed
red jobs stopped at the expected release-intent guard for one exact SHA.
"""
import argparse
import json
from pathlib import Path
import re
import sys

SCHEMA = "nexus.release-intent-triage.v1"
# These checks MUST remain failures. Do not change release workflows.
EXPECTED = {
    "v1.6": ("Fail-closed release intent gate",
             "release(v1.6): request exact-candidate seal"),
    "v1.7": ("Fail-closed v1.7 release intent gate",
             "release(v1.7): request exact-candidate seal"),
    "v2.1": ("Require explicit exact-candidate release intent",
             "release(v2.1): request capability-enforcement seal"),
    "v2.2": ("Require explicit exact-candidate release intent",
             "release(v2.2): request revocation-replay seal"),
    "v2.3": ("Require explicit exact-candidate release intent",
             "release(v2.3): request stale-authority-defense seal"),
    "v2.4": ("Require explicit exact-candidate release intent",
             "release(v2.4): request gateway-authority-confusion seal"),
    "v2.5": ("Require explicit exact-candidate release intent",
             "release(v2.5): request unified-transport-authentication seal"),
}


class EvidenceBlocked(ValueError):
    pass


def require(ok):
    if not ok:
        raise EvidenceBlocked("missing, mismatched or unexpected release-gate evidence")


def classify(document):
    require(type(document) is dict and
            set(document) == {"schema", "sha", "commit_message", "runs"})
    require(document["schema"] == SCHEMA)
    sha = document["sha"]
    require(type(sha) is str and re.fullmatch(r"[0-9a-f]{40}", sha))
    message = document["commit_message"]
    require(type(message) is str and 0 < len(message) <= 16000)
    runs = document["runs"]
    require(type(runs) is list and len(runs) == len(EXPECTED))
    observed = set()
    for run in runs:
        require(type(run) is dict and
                set(run) == {"version", "name", "head_sha", "status",
                             "conclusion", "failed_steps"})
        version = run["version"]
        require(type(version) is str and version in EXPECTED and
                version not in observed)
        observed.add(version)
        expected_step, exact_intent = EXPECTED[version]
        require(run["name"] == f"NEXUS {version} Release Gate")
        require(run["head_sha"] == sha)
        require(run["status"] == "completed" and run["conclusion"] == "failure")
        require(type(run["failed_steps"]) is list and
                run["failed_steps"] == [expected_step])
        # If this exact commit DID request the release, stopping at its intent
        # guard would be unexpected, not a reassuring "expected refusal".
        require(message != exact_intent)
    require(observed == set(EXPECTED))
    return {
        "schema": SCHEMA,
        "status": "EXPECTED_INTENT_REFUSALS_ONLY",
        "classified_versions": sorted(observed),
        "observed_refusal_count": len(observed),
        "engineering_tests": "not_evaluated",
        "real_backup": "not_evaluated",
        "production_recovery": "not_evaluated",
        "release_authorized": False,
        "seal_granted": False,
        "authority": "none",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("evidence", type=Path,
                   help="private or synthetic UTF-8 sanitized metadata JSON")
    args = p.parse_args()
    try:
        # File size bound and no path/content echo: evidence may be private.
        require(args.evidence.is_file() and not args.evidence.is_symlink() and
                args.evidence.stat().st_size <= 128 * 1024)
        raw = args.evidence.read_text(encoding="utf-8")
        def no_duplicate_keys(pairs):
            result = {}
            for key, value in pairs:
                require(key not in result)
                result[key] = value
            return result
        report = classify(json.loads(raw, object_pairs_hook=no_duplicate_keys))
        print(json.dumps(report, sort_keys=True))
        return 0
    except (ValueError, OSError, UnicodeError, TypeError):
        print("RELEASE INTENT TRIAGE: UNVERIFIED OR UNEXPECTED (NOT A RELEASE PASS)",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
