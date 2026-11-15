#!/usr/bin/env python3
"""Adversarial 2-of-2 ED25519 synthetic OCI review and admission denial tests."""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
CLI = HERE / "stage-d-two-reviewer-admission.py"
SIGNER = HERE / "stage-d-signed-oci-admission.py"
REV = "a" * 40

spec = importlib.util.spec_from_file_location(
    "nexus_stage242_stage240_fixture", HERE / "test-stage-d-oci-image-evidence.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def canonical(obj):
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":")) + "\n").encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def run(executable, cli, good=True):
    p = subprocess.run([sys.executable, str(executable), *map(str, cli)],
                       capture_output=True, text=True, timeout=35)
    if (p.returncode == 0) != good:
        raise AssertionError(
            f"unexpected result {p.returncode}; stdout={p.stdout}; stderr={p.stderr}")
    if not good and ("DENIED" not in p.stderr and "BLOCKED" not in p.stderr):
        raise AssertionError("missing fail-closed denial marker")
    return p


def openssl(*argv):
    return subprocess.run(["openssl", *map(str, argv)], check=True,
                          capture_output=True, timeout=20).stdout


def deployment_intent(image, manifest_sha):
    return {
        "schema": "nexus.stage-d.synthetic-oci-deployment-policy.v1",
        "scope": "synthetic-only",
        "reviewed_pr_commit": REV,
        "evidence_manifest_sha256": manifest_sha,
        "local_image_id": image,
        "requested_registry_digest": None,
        "network_policy": "isolated-loopback-only",
        "data_policy": "new-disposable-synthetic-volume",
        "container_user": "10001:10001",
        "expected_entrypoint": [
            "/usr/local/bin/python3", "-I", "-B",
            "/opt/nexus/stage-d-guarded-image-entrypoint.py",
        ],
        "entrypoint_override_allowed": False,
        "privileged_allowed": False,
        "privilege_escalation_allowed": False,
        "host_paths_allowed": False,
        "production_credentials_allowed": False,
        "live_provider_allowed": False,
        "deployment_authorized": False,
    }


def candidate(image):
    return {
        "schema": "nexus.stage-d.synthetic-nonexecuting-launch.v1",
        "image": image,
        "image_source": "local-unpublished",
        "image_pull_policy": "never",
        "user": "10001:10001",
        "entrypoint": [
            "/usr/local/bin/python3", "-I", "-B",
            "/opt/nexus/stage-d-guarded-image-entrypoint.py",
        ],
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


def main():
    count = 0
    with tempfile.TemporaryDirectory(prefix="nexus-two-ed25519-reviews-") as tmp:
        root = Path(tmp)
        manifest_doc, sbom_doc = fixture.template()
        manifest_path, sbom_path = root / "manifest.json", root / "sbom.json"
        manifest_path.write_bytes(canonical(manifest_doc))
        sbom_path.write_bytes(canonical(sbom_doc))
        manifest_sha = sha(manifest_path.read_bytes())
        sbom_sha = sha(sbom_path.read_bytes())
        reviewers = {}
        for role in ("build", "recovery"):
            private = root / (role + "-private.pem")
            public = root / (role + "-public.pem")
            signed = root / (role + "-review.json")
            openssl("genpkey", "-algorithm", "Ed25519", "-out", private)
            os.chmod(private, 0o600)
            public.write_bytes(openssl("pkey", "-in", private, "-pubout"))
            der = sha(openssl("pkey", "-pubin", "-in", public, "-outform", "DER"))
            ident = role + "-synthetic-test"
            inputs = [
                "--manifest", manifest_path, "--sbom", sbom_path,
                "--reviewed-commit", REV,
                "--expected-manifest-sha256", manifest_sha,
                "--expected-sbom-sha256", sbom_sha,
                "--local-image-id", manifest_doc["local_oci_image_id"],
                "--reviewer-key-id", ident,
                "--public-key", public,
                "--public-key-der-sha256", der,
                "--signed-review", signed,
                "--private-key", private,
            ]
            result = json.loads(run(SIGNER, ["sign-synthetic", *inputs]).stdout)
            assert result["release_gate"] == "BLOCKED"
            reviewers[role] = {
                "key-id": ident, "public-key": public,
                "public-der-sha256": der, "review": signed,
                "review-sha256": sha(signed.read_bytes()),
                "private": private,
            }
            count += 1

        assert reviewers["build"]["public-der-sha256"] != reviewers["recovery"]["public-der-sha256"]
        count += 1
        plan_path, spec_path = root / "deployment-intent.json", root / "candidate.json"
        plan = deployment_intent(manifest_doc["local_oci_image_id"], manifest_sha)
        cfg = candidate(manifest_doc["local_oci_image_id"])
        plan_path.write_bytes(canonical(plan))
        spec_path.write_bytes(canonical(cfg))

        def cli():
            values = [
                "--manifest", manifest_path, "--sbom", sbom_path,
                "--reviewed-commit", REV,
                "--expected-manifest-sha256", manifest_sha,
                "--expected-sbom-sha256", sbom_sha,
                "--local-image-id", manifest_doc["local_oci_image_id"],
                "--deployment-intent", plan_path,
                "--expected-intent-sha256", sha(plan_path.read_bytes()),
                "--candidate-spec", spec_path,
                "--candidate-spec-sha256", sha(spec_path.read_bytes()),
            ]
            for role in ("build", "recovery"):
                for k in ("key-id", "public-key", "public-der-sha256",
                          "review", "review-sha256"):
                    values += ["--" + role + "-" + k, reviewers[role][k]]
            return values

        report = json.loads(run(CLI, ["inspect-pair", *cli()]).stdout)
        assert report["status"] == "TWO_DISTINCT_ED25519_SYNTHETIC_REVIEWS_VERIFIED"
        assert report["distinct_cryptographic_public_keys"] is True
        assert report["different_physical_custody_proven"] is False
        assert report["build_provenance_independently_attested"] is False
        assert report["production_release_authorized"] is False
        assert report["release_gate"] == "BLOCKED"
        count += 1

        blocked = run(CLI, ["admission-gate", *cli()], good=False)
        assert json.loads(blocked.stdout)["release_gate"] == "BLOCKED"
        count += 1

        def denied(options=None, mode="inspect-pair"):
            nonlocal count
            run(CLI, [mode, *(cli() if options is None else options)], good=False)
            count += 1

        # Reuse same identity, signed bytes, or public key even if the
        # peer role's other fields remain syntactically coherent.
        for field in ("key-id", "public-key", "public-der-sha256",
                      "review", "review-sha256"):
            options = cli()
            original = "--build-" + field
            target = "--recovery-" + field
            options[options.index(target) + 1] = options[options.index(original) + 1]
            denied(options)
        for field, value in (
            ("--build-review-sha256", "0" * 64),
            ("--recovery-review-sha256", "1" * 64),
            ("--build-public-der-sha256", "2" * 64),
            ("--recovery-public-der-sha256", "3" * 64),
            ("--expected-manifest-sha256", "4" * 64),
            ("--expected-sbom-sha256", "5" * 64),
            ("--expected-intent-sha256", "6" * 64),
            ("--candidate-spec-sha256", "7" * 64),
            ("--local-image-id", "sha256:" + "f" * 64),
            ("--reviewed-commit", "f" * 40),
        ):
            options = cli()
            options[options.index(field) + 1] = value
            denied(options)

        original_spec = canonical(cfg)
        for field, value in (
            ("schema", "production-spec"),
            ("image", "sha256:" + "1" * 64),
            ("image_source", "registry-published"),
            ("image_pull_policy", "always"),
            ("user", "0:0"),
            ("entrypoint", ["/opt/nexus/nexus"]),
            ("command", ["--unsafe"]),
            ("read_only_root", False),
            ("network", "host"),
            ("drop_all_capabilities", False),
            ("no_new_privileges", False),
            ("allow_privileged", True),
            ("allow_host_pid", True),
            ("allow_host_network", True),
            ("mounts", [{"destination": "/data",
                         "source_kind": "existing-production-volume",
                         "read_only": False}]),
            ("production_service_selected", True),
            ("production_data_present", True),
            ("deployment_approved", True),
        ):
            invalid = deepcopy(cfg)
            invalid[field] = value
            spec_path.write_bytes(canonical(invalid))
            denied()
        invalid = deepcopy(cfg)
        invalid["allow_entrypoint_override"] = True
        spec_path.write_bytes(canonical(invalid))
        denied()
        spec_path.write_bytes(original_spec)

        plan_path.write_bytes(canonical(dict(plan, live_provider_allowed=True)))
        denied()
        plan_path.write_bytes(canonical(plan))

        original_review = reviewers["build"]["review"].read_bytes()
        corrupt = json.loads(original_review)
        corrupt["scope"] = "production"
        reviewers["build"]["review"].write_bytes(canonical(corrupt))
        options = cli()
        options[options.index("--build-review-sha256") + 1] = sha(
            reviewers["build"]["review"].read_bytes())
        denied(options)
        reviewers["build"]["review"].write_bytes(original_review)

        foreign = root / "alias.json"
        foreign.symlink_to(reviewers["recovery"]["review"])
        options = cli()
        options[options.index("--recovery-review") + 1] = foreign
        denied(options)

        # Even when two signatures pass, the release gate MUST fail closed.
        assert run(CLI, ["admission-gate", *cli()], good=False).returncode != 0
        count += 1

    print(json.dumps({
        "status": "PASS", "checks": count,
        "scope": "synthetic-two-distinct-Ed25519-reviewers-and-deny-only-image-admission",
        "actual_separate_physical_key_custody_proven": False,
        "registry_image_digest_verified": False,
        "production_release_authorized": False,
        "live_provider_mutated": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
