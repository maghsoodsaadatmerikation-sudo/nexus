#!/usr/bin/env python3
"""Fail-closed evidence of an exact four-PR source assembly, not a release gate.

The manifest pins exact original Git blob identities. A manual CI reconciliation
is checked for retained tests. Does not fetch GitHub/provider data or grant
merge/deployment authority. Git SHA-1 is a source identity format, not attestation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "integration/execution-readiness-manifest.json"
SCHEMA = "nexus.execution-readiness-assembly.v1"
BASE_SHA = "b7855b1a1bb9f3776e8f24b682d124cbe334543e"
ORIGINS = {
    187: ("92bc3879bd102d0e9c05bdbc4bad8203af572c4c", (
        "docs/gateway-health.md",
        "scripts/observe-pilot-runtime.py",
        "scripts/test-observe-pilot-runtime.py",
    )),
    188: ("851e68aec2416bd6a54ea3a0e734e0205347c685", (
        ".github/workflows/production-freeze-preflight.yml",
        "docs/PRODUCTION-FREEZE-PREFLIGHT.md",
        "scripts/production-freeze-preflight.py",
        "scripts/test-production-freeze-preflight.py",
    )),
    189: ("e0660f330ee80f6ed12db44730cb594cc7bf5703", (
        ".github/workflows/pilot-cross-runner-recovery.yml",
        "docs/PILOT-CROSS-RUNNER-RECOVERY.md",
        "scripts/pilot-cross-runner-recovery.py",
    )),
    190: ("ede84d8bd3c98429e389feca656cee892eeaf14f", (
        ".github/workflows/stage-d-operator-transport.yml",
        "docs/STAGE-D-OPERATOR-TRANSPORT.md",
        "ops/stage-d-operator.Dockerfile",
        "ops/stage_d_operator.py",
        "ops/stage_d_transport.py",
        "scripts/test-stage-d-operator-transport.py",
    )),
}
REQUIRED_PRIMARY = (
    "python3 scripts/test-observe-pilot-runtime.py",
    "python3 scripts/test-production-freeze-preflight.py",
    "python3 scripts/test-stage-d-operator-transport.py",
)
REQUIRED_WORKFLOWS = (
    ".github/workflows/pr-verify.yml",
    ".github/workflows/production-freeze-preflight.yml",
    ".github/workflows/pilot-cross-runner-recovery.yml",
    ".github/workflows/stage-d-operator-transport.yml",
)
SOURCE_FIELDS = {"path", "pr", "source_commit", "blob_sha"}
MANIFEST_FIELDS = {
    "schema", "base_sha", "assembly", "inputs", "manually_reconciled",
    "production_recovery_verified", "render_autodeploy_disabled_verified",
    "strict_ruleset_enabled_verified", "release_authorized", "authority",
}


class AssemblyBlocked(ValueError):
    pass


def require(ok, code):
    if not ok:
        raise AssemblyBlocked(code)


def unique_object(pairs):
    out = {}
    for k, v in pairs:
        require(k not in out, "duplicate-json-key")
        out[k] = v
    return out


def forbidden_number(_):
    raise AssemblyBlocked("non-finite-number")


def blob_identity(contents):
    return hashlib.sha1(
        b"blob " + str(len(contents)).encode("ascii") + b"\0" + contents
    ).hexdigest()


def load(path=MANIFEST):
    require(path.is_file() and not path.is_symlink(), "unsafe-manifest")
    require(0 < path.stat().st_size <= 32768, "unbounded-manifest")
    return json.loads(
        path.read_bytes(),
        object_pairs_hook=unique_object,
        parse_constant=forbidden_number,
    )


def verify(manifest, root=ROOT):
    require(type(manifest) is dict and set(manifest) == MANIFEST_FIELDS,
            "manifest-envelope")
    require(manifest["schema"] == SCHEMA, "manifest-schema")
    require(manifest["base_sha"] == BASE_SHA, "unknown-assembly-base")
    require(manifest["assembly"] == "unprivileged-source-only",
            "wrong-assembly-kind")
    require(manifest["manually_reconciled"] == [".github/workflows/pr-verify.yml"],
            "untracked-manual-reconciliation")
    for field in ("production_recovery_verified", "render_autodeploy_disabled_verified",
                  "strict_ruleset_enabled_verified", "release_authorized"):
        require(manifest[field] is False, "source-claims-production")
    require(manifest["authority"] == "none", "authority-expansion")

    expected = {p: (n, sha) for n, (sha, paths) in ORIGINS.items() for p in paths}
    inputs = manifest["inputs"]
    require(type(inputs) is list and len(inputs) == len(expected),
            "unexpected-file-count")
    seen = set()
    for item in inputs:
        require(type(item) is dict and set(item) == SOURCE_FIELDS, "invalid-file-entry")
        path = item["path"]
        require(type(path) is str and path in expected and path not in seen,
                "foreign-or-duplicate-path")
        seen.add(path)
        number, commit = expected[path]
        require(type(item["pr"]) is int and item["pr"] == number and
                item["source_commit"] == commit, "source-binding-changed")
        sha = item["blob_sha"]
        require(type(sha) is str and re.fullmatch(r"[0-9a-f]{40}", sha),
                "invalid-blob-identity")
        f = root / path
        require(f.is_file() and not f.is_symlink(), "source-not-regular-file")
        require(blob_identity(f.read_bytes()) == sha, "source-byte-drift")
    require(seen == set(expected), "missing-source-file")

    ci = root / ".github/workflows/pr-verify.yml"
    require(ci.is_file() and not ci.is_symlink(), "primary-ci-missing")
    main = ci.read_text(encoding="utf-8")
    for test in REQUIRED_PRIMARY:
        require(main.count(test) == 1, "ci-test-missing-or-duplicated")
    require("name: readonly-verification" in main and
            "pull_request_target" not in main and
            "permissions:\n  contents: read" in main,
            "primary-ci-authority-drift")

    for name in REQUIRED_WORKFLOWS:
        workflow = root / name
        require(workflow.is_file() and not workflow.is_symlink(),
                "workflow-missing")
        source = workflow.read_text(encoding="utf-8")
        require("permissions:\n  contents: read" in source and
                "persist-credentials: false" in source and
                "pull_request_target" not in source and
                "ref: " + "$" + "{{ github.sha }}" in source,
                "workflow-privilege-drift")

    return {
        "schema": SCHEMA,
        "status": "SOURCE_ASSEMBLY_VERIFIED",
        "original_source_prs": sorted(ORIGINS),
        "exact_blob_files": len(seen),
        "manually_reconciled_primary_ci_tests": len(REQUIRED_PRIMARY),
        "production_backup_inspected": False,
        "production_restore_verified": False,
        "live_deploy_settings_changed": False,
        "merge_authorized": False,
        "release_authorized": False,
        "authority": "none",
    }


def main():
    try:
        print(json.dumps(verify(load()), sort_keys=True))
        return 0
    except (AssemblyBlocked, OSError, UnicodeError, ValueError, TypeError):
        print("NEXUS ASSEMBLY: BLOCKED (not deployment evidence)", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
