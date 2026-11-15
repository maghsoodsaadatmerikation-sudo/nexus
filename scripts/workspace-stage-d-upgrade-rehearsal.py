#!/usr/bin/env python3
"""Offline, non-executable safe upgrade/recovery rehearsal contract for Stage D.

All provider and Git graph inputs require independent exact SHA-256 pins.
This tool NEVER deploys, changes Railway, migrates schemas, signs approvals,
reverts real data, or asserts that a binary rollback is safe for the data.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "nexus_stage_d_rehearsal_coherence",
    HERE / "workspace-stage-d-deploy-coherence.py")
if spec is None or spec.loader is None:
    raise RuntimeError("Stage D commit verifier unavailable")
coherence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coherence)
provider = coherence.preflight

SCHEMA = "nexus.stage-d.nonexecuting-upgrade-rehearsal.v1"
REPORT_SCHEMA = "nexus.stage-d.nonexecuting-upgrade-report.v1"
COMPARE_LIMIT = 4 * 1024 * 1024
PLAN_FIELDS = frozenset({
    "schema", "project_id", "environment_id", "repository",
    "source_service_id", "restore_service_id",
    "source_volume_id", "restore_volume_id",
    "source_current_commit", "restore_current_commit",
    "proposed_rehearsal_commit", "source_fallback_commit",
    "restore_fallback_commit", "run_mode", "destination_policy",
    "permit_source_volume_write", "permit_restore_volume_write",
    "permit_destructive_test", "permit_apply_provider_patch",
    "permit_deploy_or_wake", "permit_signer_rotation",
    "require_independent_backup_and_checkpoint",
    "require_data_schema_rollback_review",
})


class RehearsalError(Exception):
    pass


def deny(msg):
    raise RehearsalError(msg)


def commit(value, label):
    if not isinstance(value, str) or not coherence.COMMIT.fullmatch(value):
        deny(label + " must be an exact lowercase 40-character Git commit SHA")
    return value


def field_match(plan, key, expected):
    if plan[key] != expected:
        deny("operator plan " + key + " differs from separately pinned provider identity")


def load_plan(args):
    data = provider.exact_snapshot(args.plan, args.plan_sha256, "operator rehearsal plan")
    if set(data) != PLAN_FIELDS or data["schema"] != SCHEMA:
        deny("operator rehearsal plan must use exactly the reviewed v1 schema")
    for name in ("source_current_commit", "restore_current_commit",
                 "proposed_rehearsal_commit", "source_fallback_commit",
                 "restore_fallback_commit"):
        commit(data[name], name)
    for flag in (
        "permit_source_volume_write", "permit_restore_volume_write",
        "permit_destructive_test", "permit_apply_provider_patch",
        "permit_deploy_or_wake", "permit_signer_rotation",
    ):
        if data[flag] is not False:
            deny("rehearsal must explicitly forbid: " + flag)
    for flag in (
        "require_independent_backup_and_checkpoint",
        "require_data_schema_rollback_review",
    ):
        if data[flag] is not True:
            deny("rehearsal must preserve required prerequisite: " + flag)
    if (data["run_mode"] != "review-only"
            or data["destination_policy"] != "new-disposable-isolated-volume"):
        deny("rehearsal does not authorize executable changes or live volume reuse")
    for name, expected in (
        ("project_id", args.project_id),
        ("environment_id", args.environment_id),
        ("repository", args.expected_repo),
        ("source_service_id", args.source_service_id),
        ("restore_service_id", args.restore_service_id),
        ("source_volume_id", args.source_volume_id),
        ("restore_volume_id", args.restore_volume_id),
    ):
        field_match(data, name, expected)
    if (data["source_fallback_commit"] != data["source_current_commit"]
            or data["restore_fallback_commit"] != data["restore_current_commit"]):
        deny("fallback code revisions must reference the actual pre-rehearsal states")
    if data["source_current_commit"] == data["restore_current_commit"]:
        deny("this staged upgrade plan requires explicit observed version skew")
    return data


def read_comparison(path, pin, repo, old, new, label):
    obj = provider.exact_snapshot(path, pin, label + " GitHub comparison")
    if (obj.get("repository_full_name") != repo
            or obj.get("base") != old or obj.get("head") != new):
        deny(label + " graph comparison does not bind to approved repository and endpoints")
    if obj.get("too_large") is True:
        deny(label + " GitHub comparison is truncated; full ancestry not established")
    base_commit = provider.obj(obj.get("base_commit"), label + " base commit")
    merge_base = provider.obj(obj.get("merge_base_commit"), label + " merge-base")
    if base_commit.get("sha") != old or merge_base.get("sha") != old:
        deny(label + " is not a confirmed direct ancestor in the supplied graph snapshot")
    ahead = obj.get("ahead_by")
    behind = obj.get("behind_by")
    total = obj.get("total_commits")
    if (type(ahead) is not int or type(behind) is not int
            or type(total) is not int or behind != 0
            or not 0 <= ahead <= 10000 or total != ahead):
        deny(label + " contains inconsistent or ambiguous ancestry counts")
    if (old == new and (obj.get("status") != "identical" or ahead != 0))
            or (old != new and (obj.get("status") != "ahead" or ahead == 0))):
        deny(label + " comparison does not prove a monotonic proposed code path")
    # These values are untrusted provider graph metadata, NOT security attestations.
    return ahead


def deployments(args, plan):
    result = coherence.verify(args)
    if result["source"]["reported_git_commit"] != plan["source_current_commit"]:
        deny("operator plan misstates deployed source commit")
    if result["recovery"]["reported_git_commit"] != plan["restore_current_commit"]:
        deny("operator plan misstates deployed restore commit")
    return result


def verify(args):
    plan = load_plan(args)
    # The prior provider verifier requires a single target commit; choose
    # the operator's proposed rehearsal revision to expose exact drift.
    args.expected_commit = plan["proposed_rehearsal_commit"]
    reported = deployments(args, plan)
    gap = read_comparison(
        args.restore_to_source, args.restore_to_source_sha256,
        args.expected_repo, plan["restore_current_commit"],
        plan["source_current_commit"], "restore-to-source")
    forward = read_comparison(
        args.source_to_target, args.source_to_target_sha256,
        args.expected_repo, plan["source_current_commit"],
        plan["proposed_rehearsal_commit"], "source-to-target")

    blockers = set(reported["blocked_reasons"])
    blockers.update({
        "separate_verified_encrypted_offhost_backup_missing",
        "external_monotonic_checkpoint_and_witness_review_missing",
        "isolated_disposable_restore_volume_not_provisioned_or_verified",
        "database_and_state_schema_backward_compatibility_unproved",
        "code_rollback_does_not_undo_state_schema_migration",
        "actual_synthetic_to_real_cross_host_drill_not_performed",
        "release_and_recovery_operator_approval_missing",
    })
    if gap:
        blockers.add("restore_deployment_trails_source_by_" + str(gap) + "_commits")
    if forward:
        blockers.add("proposed_code_rehearsal_ahead_of_source_by_" + str(forward) + "_commits")
    return {
        "schema": REPORT_SCHEMA,
        "status": "reviewed-offline-upgrade-rehearsal-only",
        "plan_sha256": args.plan_sha256,
        "observed_source_git_commit": plan["source_current_commit"],
        "observed_recovery_git_commit": plan["restore_current_commit"],
        "proposed_rehearsal_git_commit": plan["proposed_rehearsal_commit"],
        "recovery_to_source_ancestor_steps": gap,
        "source_to_target_ancestor_steps": forward,
        "source_code_fallback_commit": plan["source_fallback_commit"],
        "recovery_code_fallback_commit": plan["restore_fallback_commit"],
        "rehearsal_order": [
            "retain independently pinned before-state and approved immutable snapshot",
            "obtain reviewed schema compatibility contract and checksum manifest",
            "provision separately approved disposable isolated restore volume",
            "validate signed restore in isolated environment without touching existing mounts",
            "rehearse candidate image in isolation against copied non-sensitive fixture",
            "verify witness challenge, dataset equivalence and safety before human review",
            "on failure freeze changes; restore approved immutable snapshot to disposable recovery",
            "never apply code-only rollback to a migrated live persistent volume",
        ],
        "blocked_reasons": sorted(blockers),
        "git_metadata_direct_ancestry_consistent": True,
        "actual_rehearsal_executed": False,
        "real_rollback_tested": False,
        "original_volumes_mutated": False,
        "provider_release_authorized": False,
        "release_gate": "BLOCKED",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("inspect", "release-gate"))
    for name in ("inventory", "health", "source-deployments", "restore-deployments",
                 "restore-to-source", "source-to-target", "plan"):
        parser.add_argument("--" + name, type=Path, required=True)
        parser.add_argument("--" + name + "-sha256", required=True)
    for name in ("project-id", "environment-id", "expected-repo",
                 "source-service-id", "restore-service-id",
                 "source-volume-id", "restore-volume-id"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    try:
        result = verify(args)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        if args.mode == "release-gate":
            print("NEXUS STAGE D REHEARSAL RELEASE: BLOCKED; no validated real-host migration or rollback", file=sys.stderr)
            return 1
        return 0
    except (RehearsalError, coherence.CoherenceError,
            provider.ProviderError, provider.trust.TrustError,
            OSError, ValueError, TypeError, KeyError) as err:
        print("NEXUS STAGE D REHEARSAL DENIED: " + str(err), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
