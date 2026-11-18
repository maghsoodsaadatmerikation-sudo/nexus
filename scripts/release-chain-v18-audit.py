#!/usr/bin/env python3
"""Read-only audit of the v1.8 NEXUS Verification -> Rebuild run chain.

This establishes identity and evidence *consistency*, not a general release
authorization. The calling workflow must independently verify the downloaded
evidence file's GitHub/Sigstore attestation BEFORE running this validator.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

_BASE = Path(__file__).with_name("release-run-provenance.py")
_spec = importlib.util.spec_from_file_location("nexus_release_run_provenance", _BASE)
if _spec is None or _spec.loader is None:
    raise RuntimeError("release provenance validator is unavailable")
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)

ProvenanceError = _core.ProvenanceError
require = _core.require
read_json = _core.read_json
nested = _core.nested
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SCHEMA = "nexus.v1.8.independent-rebuild-evidence.v1"
_ENVIRONMENT = "github-hosted ubuntu-24.04"
_EXPECTED_EVIDENCE_KEYS = frozenset({
    "schema", "status", "candidate_sha", "nexus_verification_run_id",
    "independent_rebuild_run_id", "builders", "executable_digest_match",
    "production_mutation_performed", "paid_upgrade_required",
    "secret_value_recorded", "authority_expansion", "claim_boundary",
})


def validate_chain(*, repo: str, sha: str, workflow_sha: str, parent_id: int,
                   rebuild_id: int, parent: dict, rebuild: dict, evidence: dict,
                   repository: dict, main_branch: dict) -> dict:
    # Parent must actually be a first-attempt push-success in this exact
    # repository and on the exact current main commit.
    _core.validate(
        release="v1.6", repo=repo, run_id=parent_id, sha=sha,
        workflow_sha=workflow_sha, run=parent, repository=repository,
        main_branch=main_branch,
    )
    require(type(rebuild_id) is int and rebuild_id > 0 and rebuild_id != parent_id,
            "invalid or identical rebuild run ID")
    require(type(rebuild) is dict, "missing rebuild run object")
    expected_name, expected_path = _core.SOURCE_WORKFLOWS["v1.8"]
    require(rebuild.get("id") == rebuild_id and type(rebuild.get("id")) is int,
            "rebuild run ID mismatch")
    require(rebuild.get("name") == expected_name
            and rebuild.get("path") == expected_path,
            "rebuild workflow name/path mismatch")
    require(rebuild.get("event") == "workflow_run"
            and rebuild.get("head_branch") == "main",
            "rebuild must be a chained workflow_run on main")
    require(rebuild.get("status") == "completed"
            and rebuild.get("conclusion") == "success",
            "rebuild not completed successfully")
    require(type(rebuild.get("run_attempt")) is int and rebuild["run_attempt"] == 1,
            "rebuild rerun/unknown attempt denied")
    require(rebuild.get("head_sha") == sha, "rebuild SHA mismatch")
    if nested(rebuild, "head_commit", "id") is not None:
        require(nested(rebuild, "head_commit", "id") == sha,
                "rebuild head commit mismatch")
    require(nested(rebuild, "repository", "id") == repository["id"]
            and nested(rebuild, "repository", "full_name") == repo,
            "rebuild repository mismatch")
    require(nested(rebuild, "head_repository", "id") == repository["id"]
            and nested(rebuild, "head_repository", "full_name") == repo,
            "rebuild fork/ambiguous head repository")

    require(type(evidence) is dict
            and frozenset(evidence) == _EXPECTED_EVIDENCE_KEYS,
            "rebuild evidence missing, unexpected or ambiguous fields")
    require(evidence["schema"] == _SCHEMA and evidence["status"] == "PASS",
            "invalid rebuild evidence schema/status")
    require(evidence["candidate_sha"] == sha, "evidence candidate SHA mismatch")
    require(type(evidence["nexus_verification_run_id"]) is int
            and evidence["nexus_verification_run_id"] == parent_id,
            "evidence parent run ID mismatch")
    require(type(evidence["independent_rebuild_run_id"]) is int
            and evidence["independent_rebuild_run_id"] == rebuild_id,
            "evidence rebuild run ID mismatch")
    require(type(evidence["builders"]) is dict
            and set(evidence["builders"]) == {"a", "b"},
            "two exact builder witnesses required")
    hashes = []
    for name in ("a", "b"):
        builder = evidence["builders"][name]
        require(type(builder) is dict
                and set(builder) == {"environment", "executable_sha256"},
                f"invalid builder {name}")
        require(builder["environment"] == _ENVIRONMENT,
                f"unexpected builder {name} environment")
        digest = builder["executable_sha256"]
        require(type(digest) is str and _SHA256.fullmatch(digest) is not None,
                f"invalid builder {name} digest")
        hashes.append(digest)
    require(hashes[0] == hashes[1]
            and evidence["executable_digest_match"] is True,
            "independent builder digests disagree")
    for key in ("production_mutation_performed", "paid_upgrade_required",
                "secret_value_recorded"):
        require(evidence[key] is False, f"unsafe or absent {key} assertion")
    require(evidence["authority_expansion"] == "NONE",
            "evidence claims unauthorized authority expansion")
    require(type(evidence["claim_boundary"]) is str
            and evidence["claim_boundary"].startswith("Byte-identical gateway executable")
            and len(evidence["claim_boundary"]) <= 300,
            "invalid evidence claim boundary")

    # Evidence names both runs, but the metadata API alone does not cryptographically
    # establish parent/child causality. GitHub attestation is verified by the
    # separate caller. This output deliberately has no authorization token.
    return {
        "status": "CONSISTENT_ONLY",
        "authority": "none",
        "release_authorized": False,
        "production_mutation": False,
        "candidate_sha": sha,
        "parent_run_id": parent_id,
        "rebuild_run_id": rebuild_id,
        "independent_executable_sha256": hashes[0],
    }


def main() -> int:
    p = argparse.ArgumentParser(description="NEXUS v1.8 two-run audit (no release)")
    p.add_argument("--repo", required=True)
    p.add_argument("--sha", required=True)
    p.add_argument("--workflow-sha", required=True)
    p.add_argument("--parent-id", type=int, required=True)
    p.add_argument("--rebuild-id", type=int, required=True)
    for key in ("parent", "rebuild", "evidence", "repo-metadata", "main"):
        p.add_argument("--" + key + "-json", type=Path, required=True)
    x = p.parse_args()
    try:
        result = validate_chain(
            repo=x.repo, sha=x.sha, workflow_sha=x.workflow_sha,
            parent_id=x.parent_id, rebuild_id=x.rebuild_id,
            parent=read_json(x.parent_json),
            rebuild=read_json(x.rebuild_json),
            evidence=read_json(x.evidence_json),
            repository=read_json(x.repo_metadata_json),
            main_branch=read_json(x.main_json),
        )
    except (ProvenanceError, OSError) as error:
        print(f"RELEASE CHAIN AUDIT: DENIED ({error})", file=sys.stderr)
        return 1
    print("RELEASE CHAIN AUDIT: CONSISTENT ONLY — no release authority")
    print(f"Candidate: {result['candidate_sha']}; independent builders: MATCH")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
