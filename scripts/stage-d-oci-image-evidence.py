#!/usr/bin/env python3
"""Capture and verify local, unsigned SYNTHETIC NEXUS OCI inventory evidence.

Source tree, immutable base index, exact binary image ID, OS package versions,
Cargo.lock dependencies, guard script digests, and partial CycloneDX inventory.
No registry publication, signature, full reproducibility or release authority.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib

SCHEMA = "nexus.stage-d.synthetic-oci-evidence.v1"
GIT_SHA = "f4d027bb5f7e715b298f7cf7184fa621a2fb071d"
PYTHON_BASE = "python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c"
RUST_BASE = "rust@sha256:0ff31c9ffa641a62e48d543fb00b4960955ea375f40776f40f585b89e654cc5e"
ENTRY = ["/usr/local/bin/python3", "-I", "-B",
         "/opt/nexus/stage-d-guarded-image-entrypoint.py"]
SCRIPTS = (
    "stage-d-guarded-image-entrypoint.py",
    "workspace-stage-d-startup-guard.py",
    "workspace-stage-d-data-rollback-screen.py",
    "workspace-stage-d-upgrade-rehearsal.py",
    "workspace-stage-d-deploy-coherence.py",
    "workspace-stage-d-railway-preflight.py",
    "workspace-trust.py", "workspace-attestation.py", "data-snapshot.py",
)
HEX = re.compile(r"[a-f0-9]{64}\Z")
GIT = re.compile(r"[a-f0-9]{40}\Z")
MAX = 2 * 1024 * 1024


class Denied(Exception):
    pass


def require(ok, reason):
    if not ok:
        raise Denied(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(obj):
    return (json.dumps(obj, ensure_ascii=False, allow_nan=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode()


def read(path):
    require(path.is_absolute() and not path.is_symlink(), "absolute regular path required")
    st = path.lstat()
    require(path.is_file() and st.st_nlink == 1 and st.st_size <= MAX,
            "unsafe or oversized source")
    data = path.read_bytes()
    require(len(data) == st.st_size, "source modified while reading")
    return data


def run(*argv):
    try:
        p = subprocess.run(argv, capture_output=True, stdin=subprocess.DEVNULL,
                           check=True, timeout=30)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise Denied("local OCI inspection command failed") from exc
    require(len(p.stdout) <= MAX, "oversized local OCI inspection")
    return p.stdout.decode()


def image_id(tag):
    try:
        found = json.loads(run("docker", "image", "inspect", tag))
    except ValueError as exc:
        raise Denied("malformed local image inspection") from exc
    require(isinstance(found, list) and len(found) == 1,
            "exactly one OCI image required")
    item = found[0]
    config = item["Config"]
    labels = config.get("Labels") or {}
    require(
        isinstance(item.get("Id"), str)
        and re.fullmatch(r"sha256:[a-f0-9]{64}", item["Id"])
        and config.get("Entrypoint") == ENTRY
        and config.get("User") == "10001:10001"
        and config.get("Cmd") in (None, [])
        and config.get("Volumes") in (None, {})
        and labels.get("nexus.runtime_scope") == "synthetic-only"
        and labels.get("nexus.release_authority") == "none"
        and labels.get("org.opencontainers.image.revision") == GIT_SHA
        and not item.get("RepoDigests"),
        "image config/identity violates synthetic-only contract")
    return item["Id"]


def packages(tag):
    # Construct dpkg-query substitutions without changing their literal text.
    fmt = "$" + "{binary:Package}" + r"\t" + "$" + "{Version}" + r"\n"
    data = run("docker", "run", "--rm", "--network", "none", "--read-only",
               "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
               "--entrypoint", "/usr/bin/dpkg-query", tag,
               "--show", "--showformat", fmt)
    items = []
    for line in data.splitlines():
        if not line:
            continue
        parts = line.split("\t")
        require(len(parts) == 2 and all(0 < len(v) <= 180 for v in parts),
                "malformed Debian package inventory")
        items.append({"type": "operating-system", "name": parts[0],
                      "version": parts[1]})
    require(10 <= len(items) <= 500 and
            len({p["name"] for p in items}) == len(items),
            "empty or ambiguous Debian dependency inventory")
    return items


def cargo(lock_path):
    try:
        doc = tomllib.loads(read(lock_path).decode())
    except ValueError as exc:
        raise Denied("malformed historical Cargo.lock") from exc
    items = []
    for p in doc.get("package", []):
        require(isinstance(p, dict) and isinstance(p.get("name"), str)
                and isinstance(p.get("version"), str), "malformed Cargo package")
        component = {"type": "library", "group": "cargo",
                     "name": p["name"], "version": p["version"]}
        if "checksum" in p:
            require(isinstance(p["checksum"], str) and HEX.fullmatch(p["checksum"]),
                    "invalid Cargo package SHA")
            component["hashes"] = [{"alg": "SHA-256", "content": p["checksum"]}]
        items.append(component)
    require(10 <= len(items) <= 1000, "missing historical Rust dependency list")
    return items


def capture(args):
    require(GIT.fullmatch(args.commit), "exact reviewed PR commit required")
    require(all(x is not None and x.is_absolute() for x in
                (args.review_root, args.build_root, args.dockerfile)),
            "explicit source checkout paths required")
    require(not args.evidence.exists() and not args.sbom.exists(),
            "capture never overwrites existing manifest/SBOM")
    df = read(args.dockerfile)
    require(df.count(b"\nFROM ") == 2 and
            ("FROM " + RUST_BASE).encode() in df and
            ("FROM " + PYTHON_BASE).encode() in df and
            b"apt-get" not in df and b"pip install" not in df and
            ("ENTRYPOINT " + json.dumps(ENTRY)).encode() in df,
            "Dockerfile uses unpinned base, mutable package installation or unsafe entrypoint")
    guarded = {}
    for name in SCRIPTS:
        path = Path("scripts") / name
        actual = read(args.review_root / path)
        require(actual == read(args.build_root / path),
                "reviewed guard differs from historical image build input")
        guarded[str(path)] = sha(actual)
    lock = read(args.build_root / "Cargo.lock")
    image = image_id(args.image)
    version = run(
        "docker", "run", "--rm", "--network", "none", "--read-only",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--entrypoint", "/usr/local/bin/python3",
        args.image, "-I", "-c", "import platform; print(platform.python_version())").strip()
    require(version == "3.12.12", "wrong pinned Python interpreter version")
    components = packages(args.image) + cargo(args.build_root / "Cargo.lock")
    components.append({"type": "library", "name": "CPython", "version": version})
    components.sort(key=lambda p: (p.get("group", ""), p["name"], p["version"]))
    sbom = {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "metadata": {"component": {
            "type": "application", "name": "nexus-stage-d-synthetic-gateway",
            "version": GIT_SHA,
        }, "properties": [
            {"name": "nexus:scope", "value": "synthetic-only"},
            {"name": "nexus:coverage", "value":
             "dpkg-installed + Cargo.lock; incomplete runtime dependency evidence"},
        ]},
        "components": components,
    }
    encoded_sbom = canonical(sbom)
    result = {
        "schema": SCHEMA, "reviewed_pr_commit": args.commit,
        "gateway_source_commit": GIT_SHA,
        "local_oci_image_id": image,
        "python_runtime_index": PYTHON_BASE,
        "rust_builder_index": RUST_BASE,
        "reviewed_dockerfile_sha256": sha(df),
        "historical_cargo_lock_sha256": sha(lock),
        "reviewed_script_sha256": guarded,
        "python_version": version,
        "partial_cyclonedx_sbom_sha256": sha(encoded_sbom),
        "sbom_components": len(components),
        "collection_scope": "unsigned-ephemeral-synthetic-only",
        "registry_digest_attested": False,
        "signed_provenance_attested": False,
        "independent_offhost_restore_proven": False,
        "release_authorized": False, "release_gate": "BLOCKED",
    }
    args.sbom.write_bytes(encoded_sbom)
    args.evidence.write_bytes(canonical(result))
    return {"status": "UNSIGNED_SYNTHETIC_EVIDENCE_CAPTURED",
            "manifest_sha256": sha(canonical(result)),
            "sbom_sha256": sha(encoded_sbom),
            "components": len(components), "release_gate": "BLOCKED"}


def verify(args):
    require(isinstance(args.expected_sha256, str) and HEX.fullmatch(args.expected_sha256),
            "independently retained exact evidence SHA is required")
    require(GIT.fullmatch(args.commit), "exact reviewed revision required")
    encoded = read(args.evidence)
    require(sha(encoded) == args.expected_sha256,
            "evidence differs from externally pinned SHA-256")
    document = json.loads(encoded)
    require(canonical(document) == encoded and
            isinstance(document, dict), "noncanonical evidence")
    fields = {
        "schema", "reviewed_pr_commit", "gateway_source_commit",
        "local_oci_image_id", "python_runtime_index", "rust_builder_index",
        "reviewed_dockerfile_sha256", "historical_cargo_lock_sha256",
        "reviewed_script_sha256", "python_version",
        "partial_cyclonedx_sbom_sha256", "sbom_components",
        "collection_scope", "registry_digest_attested",
        "signed_provenance_attested", "independent_offhost_restore_proven",
        "release_authorized", "release_gate",
    }
    require(set(document) == fields
            and document["schema"] == SCHEMA
            and document["reviewed_pr_commit"] == args.commit
            and document["gateway_source_commit"] == GIT_SHA
            and document["python_runtime_index"] == PYTHON_BASE
            and document["rust_builder_index"] == RUST_BASE
            and document["python_version"] == "3.12.12"
            and document["collection_scope"] == "unsigned-ephemeral-synthetic-only"
            and document["registry_digest_attested"] is False
            and document["signed_provenance_attested"] is False
            and document["independent_offhost_restore_proven"] is False
            and document["release_authorized"] is False
            and document["release_gate"] == "BLOCKED",
            "evidence contradicts synthetic-only release denial")
    require(isinstance(document["local_oci_image_id"], str) and
            re.fullmatch(r"sha256:[a-f0-9]{64}", document["local_oci_image_id"]),
            "local image ID missing")
    for field in ("reviewed_dockerfile_sha256", "historical_cargo_lock_sha256",
                  "partial_cyclonedx_sbom_sha256"):
        require(isinstance(document[field], str) and HEX.fullmatch(document[field]),
                "missing exact source hash")
    script_map = document["reviewed_script_sha256"]
    require(isinstance(script_map, dict)
            and set(script_map) == {"scripts/" + n for n in SCRIPTS}
            and all(isinstance(v, str) and HEX.fullmatch(v)
                    for v in script_map.values()),
            "unreviewed guard script inventory")
    sb = read(args.sbom)
    require(sha(sb) == document["partial_cyclonedx_sbom_sha256"],
            "evidence SBOM fingerprint changed")
    bom = json.loads(sb)
    require(canonical(bom) == sb and set(bom) ==
            {"bomFormat", "specVersion", "version", "metadata", "components"}
            and bom["bomFormat"] == "CycloneDX"
            and bom["specVersion"] == "1.5"
            and bom["version"] == 1
            and isinstance(bom["components"], list)
            and type(document["sbom_components"]) is int
            and 20 <= document["sbom_components"] <= 1501
            and len(bom["components"]) == document["sbom_components"],
            "malformed or incomplete partial software inventory")
    if args.image:
        require(image_id(args.image) == document["local_oci_image_id"],
                "local image no longer matches reviewed evidence")
    return {"status": "PINNED_SYNTHETIC_EVIDENCE_STRUCTURALLY_VERIFIED",
            "image_id": document["local_oci_image_id"],
            "components": document["sbom_components"],
            "release_authorized": False, "release_gate": "BLOCKED"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("capture", "verify", "release-gate"))
    p.add_argument("--image")
    p.add_argument("--evidence", required=True, type=Path)
    p.add_argument("--sbom", required=True, type=Path)
    p.add_argument("--commit", required=True)
    p.add_argument("--expected-sha256")
    p.add_argument("--review-root", type=Path)
    p.add_argument("--build-root", type=Path)
    p.add_argument("--dockerfile", type=Path)
    args = p.parse_args()
    try:
        require(args.evidence.is_absolute() and args.sbom.is_absolute(),
                "evidence and SBOM paths must be absolute")
        if args.mode == "capture":
            require(args.image and args.review_root and args.build_root
                    and args.dockerfile, "capture requires image and source roots")
            answer = capture(args)
        else:
            answer = verify(args)
        print(json.dumps(answer, sort_keys=True, separators=(",", ":")))
        if args.mode == "release-gate":
            print("NEXUS OCI RELEASE DENIED: unsigned synthetic evidence is not authorization",
                  file=sys.stderr)
            return 1
        return 0
    except (Denied, OSError, ValueError, TypeError, KeyError,
            UnicodeError) as exc:
        print("NEXUS SYNTHETIC OCI EVIDENCE DENIED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
