#!/usr/bin/env python3
"""Adversarial pinned synthetic OCI evidence verification without Docker."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
TOOL = HERE / "stage-d-oci-image-evidence.py"
REV = "a" * 40
GATEWAY = "f4d027bb5f7e715b298f7cf7184fa621a2fb071d"
PYTHON_BASE = "python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c"
RUST_BASE = "rust@sha256:0ff31c9ffa641a62e48d543fb00b4960955ea375f40776f40f585b89e654cc5e"
FILES = (
    "stage-d-guarded-image-entrypoint.py",
    "workspace-stage-d-startup-guard.py",
    "workspace-stage-d-data-rollback-screen.py",
    "workspace-stage-d-upgrade-rehearsal.py",
    "workspace-stage-d-deploy-coherence.py",
    "workspace-stage-d-railway-preflight.py",
    "workspace-trust.py", "workspace-attestation.py", "data-snapshot.py",
)


def canon(x):
    return (json.dumps(x, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def call(args, good=True):
    p = subprocess.run([sys.executable, str(TOOL), *map(str, args)],
                       capture_output=True, text=True, timeout=15)
    assert (p.returncode == 0) is good, (p.returncode, p.stdout, p.stderr)
    return p


def template():
    sbom = {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "metadata": {"component": {
            "type": "application", "name": "nexus-stage-d-synthetic-gateway",
            "version": GATEWAY,
        }, "properties": []},
        "components": [
            {"type": "operating-system", "name": "test-library-" + str(i),
             "version": "1.0"} for i in range(20)
        ],
    }
    data = {
        "schema": "nexus.stage-d.synthetic-oci-evidence.v1",
        "reviewed_pr_commit": REV,
        "gateway_source_commit": GATEWAY,
        "local_oci_image_id": "sha256:" + "b" * 64,
        "python_runtime_index": PYTHON_BASE,
        "rust_builder_index": RUST_BASE,
        "reviewed_dockerfile_sha256": "c" * 64,
        "historical_cargo_lock_sha256": "d" * 64,
        "reviewed_script_sha256": {"scripts/" + f: "e" * 64 for f in FILES},
        "python_version": "3.12.12",
        "partial_cyclonedx_sbom_sha256": sha(canon(sbom)),
        "sbom_components": 20,
        "collection_scope": "unsigned-ephemeral-synthetic-only",
        "registry_digest_attested": False,
        "signed_provenance_attested": False,
        "independent_offhost_restore_proven": False,
        "release_authorized": False,
        "release_gate": "BLOCKED",
    }
    return data, sbom


def main():
    checked = 0
    with tempfile.TemporaryDirectory(prefix="nexus-synthetic-oci-pins-") as tmp:
        root = Path(tmp)
        doc, sbom = template()
        manifest = root / "manifest.json"
        inventory = root / "sbom.json"

        def save(obj=doc, bom=sbom):
            manifest.write_bytes(canon(obj))
            inventory.write_bytes(canon(bom))
            return ["--evidence", manifest, "--sbom", inventory,
                    "--commit", REV, "--expected-sha256",
                    sha(manifest.read_bytes())]

        report = json.loads(call(["verify", *save()]).stdout)
        assert report["release_gate"] == "BLOCKED"
        assert report["release_authorized"] is False
        assert report["status"] == "PINNED_SYNTHETIC_EVIDENCE_STRUCTURALLY_VERIFIED"
        checked += 1
        gate = call(["release-gate", *save()], good=False)
        assert "BLOCKED" in gate.stdout and "DENIED" in gate.stderr
        checked += 1

        for field, value in (
            ("gateway_source_commit", "f" * 40),
            ("reviewed_pr_commit", "f" * 40),
            ("local_oci_image_id", "sha256:" + "a" * 60),
            ("python_runtime_index", "python:unreviewed"),
            ("rust_builder_index", "rust:latest"),
            ("python_version", "3.13.0"),
            ("collection_scope", "production"),
            ("registry_digest_attested", True),
            ("signed_provenance_attested", True),
            ("independent_offhost_restore_proven", True),
            ("release_authorized", True),
            ("release_gate", "PASS"),
            ("sbom_components", True),
            ("sbom_components", 0),
            ("partial_cyclonedx_sbom_sha256", "a" * 64),
            ("reviewed_script_sha256", {}),
        ):
            obj = deepcopy(doc)
            obj[field] = value
            call(["verify", *save(obj)], good=False)
            checked += 1

        obj = deepcopy(doc)
        obj["auto_deploy"] = True
        call(["verify", *save(obj)], good=False)
        checked += 1
        for field in ("dockerfile_sha256", "historical_cargo_lock_sha256"):
            obj = deepcopy(doc)
            obj["reviewed_" + field if field == "dockerfile_sha256" else field] = "f"
            call(["verify", *save(obj)], good=False)
            checked += 1

        for mutate in (
            lambda b: b.update(specVersion="1.6"),
            lambda b: b["components"].pop(),
            lambda b: b.update(components={}),
            lambda b: b.update(release_authorized=True),
        ):
            bad = deepcopy(sbom)
            mutate(bad)
            call(["verify", *save(bom=bad)], good=False)
            checked += 1

        call(["verify", *save(), "--commit", "f" * 40], good=False)
        checked += 1
        call(["verify", *save(), "--commit", "short"], good=False)
        checked += 1
        opts = save()
        opts[-1] = "0" * 64
        call(["verify", *opts], good=False)
        checked += 1

        save()
        manifest.write_bytes(manifest.read_bytes() + b" ")
        call(["verify", "--evidence", manifest, "--sbom", inventory,
              "--commit", REV, "--expected-sha256",
              sha(manifest.read_bytes())], good=False)
        checked += 1

        save()
        symlink = root / "alias.json"
        symlink.symlink_to(manifest)
        call(["verify", "--evidence", symlink, "--sbom", inventory,
              "--commit", REV, "--expected-sha256", sha(manifest.read_bytes())],
             good=False)
        checked += 1

        call(["capture", *save()], good=False)
        checked += 1

    print(json.dumps({"status": "PASS", "checks": checked,
                      "scope": "synthetic-unsigned-oci-evidence-and-hard-release-denial",
                      "real_registry_publication": False,
                      "release_authorized": False}))


if __name__ == "__main__":
    main()
