#!/usr/bin/env python3
"""Join two *CI-disposable* synthetic review signatures for the actual OCI test.

This script operates only on same-run Stage 240/241 synthetic artifacts.
It generates a second TEMPORARY Ed25519 key outside the upload directory.
Different keys do not establish different human custodians. Absolutely no
registry or provider deployment actions, keys or data are contacted.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
s = importlib.util.spec_from_file_location(
    "nexus_stage242_demo_verifier", HERE / "stage-d-two-reviewer-admission.py")
if s is None or s.loader is None:
    raise RuntimeError("NEXUS two-reviewer verifier unavailable")
quorum = importlib.util.module_from_spec(s)
s.loader.exec_module(quorum)
single = quorum.single

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def openssl(*args):
    p = subprocess.run(["openssl", *map(str, args)],
                       check=True, capture_output=True, timeout=25)
    return p.stdout

def output(path, document):
    content = single.manifest.canonical(document)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY
                 | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    return sha(content)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence-root", type=Path, required=True)
    p.add_argument("--reviewed-commit", required=True)
    p.add_argument("--synthetic-only", action="store_true", required=True)
    args = p.parse_args()
    if (not args.synthetic_only or not args.evidence_root.is_absolute()
            or args.evidence_root.is_symlink() or
            not args.evidence_root.is_dir()):
        raise RuntimeError("only exact private synthetic CI artifact directories allowed")
    root = args.evidence_root
    manifest_path = root / "manifest.json"
    sbom_path = root / "sbom.cdx.json"
    first_public = root / "ci-demo-public-ed25519.pem"
    first_report = root / "ci-demo-signed-review.json"
    reviewed = single.decode(single.read(manifest_path, single.manifest.MAX))
    if (reviewed["reviewed_pr_commit"] != args.reviewed_commit
            or reviewed["release_authorized"] is not False
            or reviewed["release_gate"] != "BLOCKED"):
        raise RuntimeError("synthetic evidence is not the exact CI-approved PR head")
    manifest_sha = sha(single.read(manifest_path, single.manifest.MAX))
    sbom_sha = sha(single.read(sbom_path, single.manifest.MAX))
    image_id = reviewed["local_oci_image_id"]
    first_der = sha(openssl("pkey", "-pubin", "-in",
                            first_public, "-outform", "DER"))
    first_review_sha = sha(single.read(first_report))
    candidate = {
        "schema": "nexus.stage-d.synthetic-nonexecuting-launch.v1",
        "image": image_id, "image_source": "local-unpublished",
        "image_pull_policy": "never", "user": "10001:10001",
        "entrypoint": single.ENTRY, "command": [],
        "read_only_root": True, "network": "none",
        "drop_all_capabilities": True, "no_new_privileges": True,
        "allow_privileged": False, "allow_host_pid": False,
        "allow_host_network": False,
        "mounts": [
            {"destination": "/data", "source_kind": "fresh-disposable-tmpfs",
             "read_only": False},
            {"destination": "/run/nexus/approval.json",
             "source_kind": "independently-pinned-policy-file",
             "read_only": True},
        ],
        "production_service_selected": False,
        "production_data_present": False, "deployment_approved": False,
    }
    intent = {
        "schema": single.PLAN_SCHEMA, "scope": "synthetic-only",
        "reviewed_pr_commit": args.reviewed_commit,
        "evidence_manifest_sha256": manifest_sha,
        "local_image_id": image_id,
        "requested_registry_digest": None,
        "network_policy": "isolated-loopback-only",
        "data_policy": "new-disposable-synthetic-volume",
        "container_user": "10001:10001",
        "expected_entrypoint": single.ENTRY,
        "entrypoint_override_allowed": False,
        "privileged_allowed": False,
        "privilege_escalation_allowed": False,
        "host_paths_allowed": False,
        "production_credentials_allowed": False,
        "live_provider_allowed": False,
        "deployment_authorized": False,
    }
    intent_path, candidate_path = (
        root / "ci-demo-dual-intent.json",
        root / "ci-demo-dual-candidate.json")
    intent_sha = output(intent_path, intent)
    candidate_sha = output(candidate_path, candidate)

    second_public = root / "ci-demo-recovery-public-ed25519.pem"
    second_report = root / "ci-demo-recovery-signed-review.json"
    with tempfile.TemporaryDirectory(prefix="nexus-ci-second-key-") as tmp:
        private = Path(tmp) / "recovery-private.pem"
        openssl("genpkey", "-algorithm", "Ed25519", "-out", private)
        os.chmod(private, 0o600)
        der = openssl("pkey", "-in", private, "-pubout")
        public_fd = os.open(second_public, os.O_EXCL | os.O_CREAT | os.O_WRONLY, 0o600)
        with os.fdopen(public_fd, "wb") as stream:
            stream.write(der)
        second_der_sha = sha(openssl(
            "pkey", "-pubin", "-in", second_public, "-outform", "DER"))
        second_ns = argparse.Namespace(
            manifest=manifest_path, sbom=sbom_path,
            reviewed_commit=args.reviewed_commit,
            expected_manifest_sha256=manifest_sha, expected_sbom_sha256=sbom_sha,
            local_image_id=image_id, reviewer_key_id="ci-demo-recovery-ephemeral",
            public_key=second_public, public_key_der_sha256=second_der_sha,
            signed_review=second_report, private_key=private)
        signed = single.sign(second_ns)
        if signed["release_gate"] != "BLOCKED":
            raise RuntimeError("synthetic second signature asserted release authority")
        second_signed_sha = signed["signed_review_sha256"]

    common = {
        "manifest": manifest_path, "sbom": sbom_path,
        "reviewed_commit": args.reviewed_commit,
        "expected_manifest_sha256": manifest_sha,
        "expected_sbom_sha256": sbom_sha,
        "local_image_id": image_id,
        "deployment_intent": intent_path,
        "expected_intent_sha256": intent_sha,
        "candidate_spec": candidate_path,
        "candidate_spec_sha256": candidate_sha,
        "build_key_id": "ci-demo-ephemeral",
        "build_public_key": first_public,
        "build_public_der_sha256": first_der,
        "build_review": first_report, "build_review_sha256": first_review_sha,
        "recovery_key_id": "ci-demo-recovery-ephemeral",
        "recovery_public_key": second_public,
        "recovery_public_der_sha256": second_der_sha,
        "recovery_review": second_report,
        "recovery_review_sha256": second_signed_sha,
    }
    admitted = quorum.verify_pair(argparse.Namespace(**common))
    if (admitted["release_gate"] != "BLOCKED"
            or admitted["different_physical_custody_proven"] is not False
            or admitted["production_release_authorized"] is not False):
        raise RuntimeError("dual CI review unexpectedly asserted production authority")
    # This is an internally produced list of same-run, NONTRUSTED pins.
    # It cannot replace externally approved, independent reference values.
    output(root / "ci-demo-dual-review-receipt.json", admitted)
    print(json.dumps({
        "status": "TWO_SYNTHETIC_CI_KEYS_SIGNED_SAME_REAL_OCI_MANIFEST",
        "build_review_sha256": first_review_sha,
        "recovery_review_sha256": second_signed_sha,
        "distinct_keys_verified": True,
        "independent_custody_proven": False,
        "registry_image_published": False,
        "real_orchestrator_policy_installed": False,
        "production_release_authorized": False,
        "release_gate": "BLOCKED",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
