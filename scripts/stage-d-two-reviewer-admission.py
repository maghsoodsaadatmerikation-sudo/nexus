#!/usr/bin/env python3
"""Verify two DISTINCT pinned Ed25519 synthetic OCI reviewers and launch policy.

This is a nonexecuting independent-review *structure* check. Distinct keys
do not prove distinct humans, hosts or administrative custody. The Docker
image has no published registry digest, and the code has no provider APIs:
no production image, manifest or deployment is authorized by a PASS.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "nexus_stage242_stage241", HERE / "stage-d-signed-oci-admission.py")
if spec is None or spec.loader is None:
    raise RuntimeError("Stage 241 detached review verifier unavailable")
single = importlib.util.module_from_spec(spec)
spec.loader.exec_module(single)

SCHEMA = "nexus.stage-d.synthetic-dual-review-admission.v1"
LAUNCH_SCHEMA = "nexus.stage-d.synthetic-nonexecuting-launch.v1"
SPEC_FIELDS = {
    "schema", "image", "image_source", "image_pull_policy",
    "user", "entrypoint", "command", "read_only_root",
    "network", "drop_all_capabilities", "no_new_privileges",
    "allow_privileged", "allow_host_pid", "allow_host_network",
    "mounts", "production_service_selected", "production_data_present",
    "deployment_approved",
}


class PairDenied(Exception):
    pass


def deny(reason):
    raise PairDenied(reason)


def reviewer_args(args, slot):
    return argparse.Namespace(
        manifest=args.manifest,
        sbom=args.sbom,
        reviewed_commit=args.reviewed_commit,
        expected_manifest_sha256=args.expected_manifest_sha256,
        expected_sbom_sha256=args.expected_sbom_sha256,
        local_image_id=args.local_image_id,
        reviewer_key_id=getattr(args, slot + "_key_id"),
        public_key=getattr(args, slot + "_public_key"),
        public_key_der_sha256=getattr(args, slot + "_public_der_sha256"),
        signed_review=getattr(args, slot + "_review"),
        expected_signed_sha256=getattr(args, slot + "_review_sha256"),
        deployment_intent=args.deployment_intent,
        expected_intent_sha256=args.expected_intent_sha256,
    )


def check_candidate_spec(args):
    if args.candidate_spec is None:
        deny("candidate policy needed even for offline synthetic review")
    raw = single.read(args.candidate_spec, 32768)
    if single.sha(raw) != single.pinned(args.candidate_spec_sha256, "candidate spec"):
        deny("candidate spec differs from externally retained exact digest")
    doc = single.decode(raw)
    if not isinstance(doc, dict) or set(doc) != SPEC_FIELDS:
        deny("candidate spec contains missing or unexpected fields")
    expected = {
        "schema": LAUNCH_SCHEMA,
        "image": args.local_image_id,
        "image_source": "local-unpublished",
        "image_pull_policy": "never",
        "user": "10001:10001",
        "entrypoint": single.ENTRY,
        "command": [],
        "read_only_root": True,
        "network": "none",
        "drop_all_capabilities": True,
        "no_new_privileges": True,
        "allow_privileged": False,
        "allow_host_pid": False,
        "allow_host_network": False,
        "mounts": [
            {"destination": "/data", "source_kind": "fresh-disposable-tmpfs",
             "read_only": False},
            {"destination": "/run/nexus/approval.json",
             "source_kind": "independently-pinned-policy-file",
             "read_only": True},
        ],
        "production_service_selected": False,
        "production_data_present": False,
        "deployment_approved": False,
    }
    if doc != expected:
        deny("candidate launch spec differs from strictly isolated plan")
    return {"candidate_spec_sha256": args.candidate_spec_sha256,
            "expected_entrypoint": single.ENTRY,
            "launch_spec_nonexecuting": True}


def verify_pair(args):
    a = reviewer_args(args, "build")
    b = reviewer_args(args, "recovery")
    if (a.reviewer_key_id == b.reviewer_key_id
            or a.public_key_der_sha256 == b.public_key_der_sha256
            or a.signed_review == b.signed_review
            or a.expected_signed_sha256 == b.expected_signed_sha256):
        deny("two separately named, signed and externally pinned distinct reviewer keys required")
    # Verify each complete signature against exactly the SAME independently
    # pinned manifest and partial SBOM. Never infer either trust anchor from
    # an untrusted signed review itself.
    verified_a = single.verify(a)
    verified_b = single.verify(b)
    if (verified_a["manifest_sha256"] != verified_b["manifest_sha256"]
            or verified_a["sbom_sha256"] != verified_b["sbom_sha256"]
            or verified_a["reviewer_public_key_der_sha256"] ==
            verified_b["reviewer_public_key_der_sha256"]):
        deny("independent signature pair does not bind one identical evidence")
    # Stage 241's strict read-only intent check is also required here.
    intent = single.admission(a)
    if intent["real_orchestrator_policy_installed"] is not False:
        deny("offline review cannot claim a live provider policy")
    candidate = check_candidate_spec(args)
    return {
        "schema": SCHEMA,
        "status": "TWO_DISTINCT_ED25519_SYNTHETIC_REVIEWS_VERIFIED",
        "reviewed_pr_commit": args.reviewed_commit,
        "evidence_manifest_sha256": args.expected_manifest_sha256,
        "sbom_sha256": args.expected_sbom_sha256,
        "local_image_id": args.local_image_id,
        "approved_reviewer_public_der_sha256": [
            verified_a["reviewer_public_key_der_sha256"],
            verified_b["reviewer_public_key_der_sha256"],
        ],
        "approved_signed_review_sha256": [
            verified_a["signed_review_sha256"],
            verified_b["signed_review_sha256"],
        ],
        "deployment_intent_sha256": args.expected_intent_sha256,
        **candidate,
        "distinct_cryptographic_public_keys": True,
        "different_human_reviewers_proven": False,
        "different_physical_custody_proven": False,
        "freshness_or_anti_replay_registry_proven": False,
        "published_registry_image_digest_verified": False,
        "build_provenance_independently_attested": False,
        "real_orchestrator_admission_policy_installed": False,
        "real_offhost_restore_proven": False,
        "live_provider_writes_performed": False,
        "production_release_authorized": False,
        "release_gate": "BLOCKED",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("inspect-pair", "admission-gate"))
    for field in ("manifest", "sbom", "deployment-intent", "candidate-spec"):
        p.add_argument("--" + field, type=Path, required=True)
    for field in ("reviewed-commit", "expected-manifest-sha256",
                  "expected-sbom-sha256", "local-image-id",
                  "expected-intent-sha256", "candidate-spec-sha256"):
        p.add_argument("--" + field, required=True)
    for slot in ("build", "recovery"):
        for field in ("public-key", "review"):
            p.add_argument("--" + slot + "-" + field, type=Path, required=True)
        for field in ("key-id", "public-der-sha256", "review-sha256"):
            p.add_argument("--" + slot + "-" + field, required=True)
    args = p.parse_args()
    try:
        result = verify_pair(args)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        if args.mode == "admission-gate":
            print(
                "NEXUS STAGE D DUAL-REVIEW ADMISSION: BLOCKED; "
                "no independent signer custody, registry digest or deployed provider control",
                file=sys.stderr)
            return 1
        return 0
    except (PairDenied, single.ReviewDenied, single.manifest.Denied,
            OSError, TypeError, ValueError, KeyError, UnicodeError) as exc:
        print("NEXUS STAGE D DUAL REVIEW DENIED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
