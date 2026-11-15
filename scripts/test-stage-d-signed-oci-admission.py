#!/usr/bin/env python3
"""Synthetic Ed25519 signed OCI evidence, tamper and admission denial tests.

Keys generated here are disposable CI fixtures, never a trusted build identity.
Every test remains synthetic-only; no real registry or provider is accessed.
"""
import base64
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
SCRIPT = HERE / "stage-d-signed-oci-admission.py"
KEYID = "ci-disposable-reviewer"
REVISION = "a" * 40

spec = importlib.util.spec_from_file_location(
    "nexus_stage241_synthetic_fixture", HERE / "test-stage-d-oci-image-evidence.py")
if spec is None or spec.loader is None:
    raise RuntimeError("Stage 240 fixture unavailable")
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def openssl(*argv):
    p = subprocess.run(["openssl", *map(str, argv)], capture_output=True,
                       timeout=15, check=True)
    return p.stdout


def run(cli, good=True):
    p = subprocess.run([sys.executable, str(SCRIPT), *map(str, cli)],
                       capture_output=True, text=True, timeout=25)
    if (p.returncode == 0) != good:
        raise AssertionError(f"bad result code={p.returncode}\n{p.stdout}\n{p.stderr}")
    if not good and "DENIED" not in p.stderr and "BLOCKED" not in p.stderr:
        raise AssertionError(f"bad denial reason {p.stderr}")
    return p


def main():
    checks = 0
    with tempfile.TemporaryDirectory(prefix="nexus-stage241-signed-oci-") as tmp:
        root = Path(tmp)
        evidence, sbom = fixtures.template()
        manifest = root / "manifest.json"
        sbom_file = root / "sbom.json"
        signed = root / "signed-review.json"
        intent = root / "deployment-intent.json"
        private = root / "ephemeral-review-key.pem"
        public = root / "ephemeral-review-public.pem"
        foreign_private = root / "foreign-key.pem"
        foreign_public = root / "foreign-public.pem"
        for key, pub in ((private, public), (foreign_private, foreign_public)):
            openssl("genpkey", "-algorithm", "Ed25519", "-out", key)
            os.chmod(key, 0o600)
            pub.write_bytes(openssl("pkey", "-in", key, "-pubout"))
            os.chmod(pub, 0o600)

        def pubfingerprint(path):
            return sha(openssl("pkey", "-pubin", "-in", path, "-outform", "DER"))

        manifest.write_bytes(canonical(evidence))
        sbom_file.write_bytes(canonical(sbom))
        base = [
            "--manifest", manifest, "--sbom", sbom_file,
            "--reviewed-commit", REVISION,
            "--expected-manifest-sha256", sha(manifest.read_bytes()),
            "--expected-sbom-sha256", sha(sbom_file.read_bytes()),
            "--local-image-id", evidence["local_oci_image_id"],
            "--public-key", public,
            "--public-key-der-sha256", pubfingerprint(public),
            "--reviewer-key-id", KEYID,
            "--signed-review", signed,
        ]

        result = json.loads(run(["sign-synthetic", *base,
                                 "--private-key", private]).stdout)
        assert result["status"] == "SYNTHETIC_REVIEW_SIGNED_NOT_DEPLOYABLE"
        assert result["production_release_authorized"] is False
        assert result["signed_review_sha256"] == sha(signed.read_bytes())
        checks += 1
        full = [*base, "--expected-signed-sha256", sha(signed.read_bytes())]
        report = json.loads(run(["verify", *full]).stdout)
        assert report["status"] == "SIGNED_SYNTHETIC_REVIEW_VERIFIED_NOT_DEPLOYABLE"
        assert report["release_gate"] == "BLOCKED"
        checks += 1

        plan = {
            "schema": "nexus.stage-d.synthetic-oci-deployment-policy.v1",
            "scope": "synthetic-only",
            "reviewed_pr_commit": REVISION,
            "evidence_manifest_sha256": sha(manifest.read_bytes()),
            "local_image_id": evidence["local_oci_image_id"],
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

        def intent_args(value=None):
            intent.write_bytes(canonical(value if value is not None else plan))
            return [*full, "--deployment-intent", intent,
                    "--expected-intent-sha256", sha(intent.read_bytes())]

        result = json.loads(run(["inspect-intent", *intent_args()]).stdout)
        assert result["status"] == "SYNTHETIC_INTENT_CONSISTENT_NOT_DEPLOYABLE"
        assert result["real_orchestrator_policy_installed"] is False
        checks += 1
        gate = run(["admission-gate", *intent_args()], good=False)
        assert "BLOCKED" in gate.stdout and "BLOCKED" in gate.stderr
        checks += 1

        run(["sign-synthetic", *base, "--private-key", private], good=False)
        checks += 1

        def changed(args, mode="verify"):
            nonlocal checks
            run([mode, *args], good=False)
            checks += 1

        for key in ("reviewed_pr_commit", "gateway_source_commit",
                    "local_oci_image_id", "release_authorized",
                    "registry_digest_attested"):
            orig = deepcopy(evidence)
            orig[key] = (True if key in ("release_authorized",
                                        "registry_digest_attested")
                         else "f" * 40 if key != "local_oci_image_id"
                         else "sha256:" + "1" * 64)
            manifest.write_bytes(canonical(orig))
            changed(full)
        manifest.write_bytes(canonical(evidence))

        for field, value in (
            ("--expected-manifest-sha256", "1" * 64),
            ("--expected-sbom-sha256", "2" * 64),
            ("--expected-signed-sha256", "3" * 64),
            ("--public-key-der-sha256", "4" * 64),
            ("--local-image-id", "sha256:" + "5" * 64),
            ("--reviewer-key-id", "other-reviewer"),
            ("--reviewed-commit", "f" * 40),
        ):
            args = list(full)
            at = args.index(field)
            args[at + 1] = value
            changed(args)

        # Re-pin the signed document even after tampering. A fresh hash is
        # not a substitute for an Ed25519 signature from the trusted key.
        pristine = json.loads(signed.read_bytes())
        for field, value in (
            ("scope", "production"),
            ("local_image_id", "sha256:" + "2" * 64),
            ("published_registry_digest", "registry.example/nexus@sha256:" + "a" * 64),
            ("production_release_authorized", True),
            ("reviewed_pr_commit", "f" * 40),
            ("reviewer_key_id", "substituted-reviewer"),
            ("signature_base64", "AA=="),
            ("independent_builder_provenance_verified", True),
        ):
            doc = deepcopy(pristine)
            doc[field] = value
            signed.write_bytes(canonical(doc))
            args = list(full)
            args[args.index("--expected-signed-sha256") + 1] = sha(signed.read_bytes())
            changed(args)
        signed.write_bytes(canonical(pristine))

        # A different Ed25519 key with a *valid external pin for itself*
        # cannot impersonate the original detached signer.
        args = list(full)
        args[args.index("--public-key") + 1] = foreign_public
        args[args.index("--public-key-der-sha256") + 1] = pubfingerprint(foreign_public)
        changed(args)

        original_sbom = sbom_file.read_bytes()
        sbom_file.write_bytes(original_sbom + b" ")
        changed(full)
        sbom_file.write_bytes(original_sbom)

        bad_double = signed.read_bytes().replace(
            b'"schema":', b'"schema":"forged","schema":', 1)
        signed.write_bytes(bad_double)
        args = list(full)
        args[args.index("--expected-signed-sha256") + 1] = sha(bad_double)
        changed(args)
        signed.write_bytes(canonical(pristine))

        link = root / "signed-alias.json"
        link.symlink_to(signed)
        args = list(full)
        args[args.index("--signed-review") + 1] = link
        changed(args)

        # Malicious deployment fields MUST be denied even if independently
        # pinned to their own malicious bytes.
        for field, value in (
            ("scope", "production"),
            ("requested_registry_digest", "registry.example/nexus@sha256:" + "a" * 64),
            ("network_policy", "public"),
            ("data_policy", "existing-production-volume"),
            ("container_user", "root"),
            ("entrypoint_override_allowed", True),
            ("privileged_allowed", True),
            ("privilege_escalation_allowed", True),
            ("host_paths_allowed", True),
            ("production_credentials_allowed", True),
            ("live_provider_allowed", True),
            ("deployment_authorized", True),
            ("reviewed_pr_commit", "f" * 40),
            ("local_image_id", "sha256:" + "f" * 64),
        ):
            altered = deepcopy(plan)
            altered[field] = value
            changed(intent_args(altered), mode="inspect-intent")

        altered = deepcopy(plan, bypass_signature=True)
        changed(intent_args(altered), mode="inspect-intent")

        intent_args()
        args = list(intent_args())
        args[args.index("--expected-intent-sha256") + 1] = "0" * 64
        changed(args, mode="inspect-intent")

        assert public.read_bytes().startswith(b"-----BEGIN PUBLIC KEY-----")
        assert private.read_bytes().startswith(b"-----BEGIN PRIVATE KEY-----")
        checks += 1

    print(json.dumps({
        "status": "PASS", "checks": checks,
        "scope": "ephemeral-Ed25519-synthetic-only-offline-admission-and-tamper-denial",
        "permanent_signing_keys_created": False,
        "real_production_deploy_performed": False,
        "registry_digest_signed": False,
        "release_authorized": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
