#!/usr/bin/env python3
"""Detached Ed25519 *synthetic-only* OCI evidence review, no deploy authority.

Signs exact Stage 240 manifest+SBOM digests with a distinct offline review
key supplied by the operator. Verifies the key against an independently pinned
DER SHA-256 and the signed artifact against an independently held exact hash.
A successful verification proves the holder of that private key signed these
bytes, not that the build is reproducible or that any runtime is deployable.
"""
import argparse
import base64
import binascii
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "nexus_stage241_manifest", HERE / "stage-d-oci-image-evidence.py")
if spec is None or spec.loader is None:
    raise RuntimeError("Stage 240 evidence verifier missing")
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)

DOMAIN = b"NEXUS\x00stage-d\x00synthetic-oci-review\x00ed25519\x00v1\x00"
SCHEMA = "nexus.stage-d.synthetic-oci-signed-review.v1"
PLAN_SCHEMA = "nexus.stage-d.synthetic-oci-deployment-policy.v1"
KEY_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
BODY_FIELDS = {
    "schema", "algorithm", "reviewer_key_id", "scope",
    "reviewed_pr_commit", "evidence_manifest_sha256", "sbom_sha256",
    "local_image_id", "published_registry_digest",
    "independent_builder_provenance_verified", "production_release_authorized",
}
SIGNED_FIELDS = BODY_FIELDS | {"signature_base64"}
PLAN_FIELDS = {
    "schema", "scope", "reviewed_pr_commit", "evidence_manifest_sha256",
    "local_image_id", "requested_registry_digest", "network_policy",
    "data_policy", "container_user", "expected_entrypoint",
    "entrypoint_override_allowed", "privileged_allowed",
    "privilege_escalation_allowed", "host_paths_allowed",
    "production_credentials_allowed", "live_provider_allowed",
    "deployment_authorized",
}
ENTRY = [
    "/usr/local/bin/python3", "-I", "-B",
    "/opt/nexus/stage-d-guarded-image-entrypoint.py",
]


class ReviewDenied(Exception):
    pass


def deny(message):
    raise ReviewDenied(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def pinned(value, name):
    if not isinstance(value, str) or not HEX.fullmatch(value):
        deny(name + " requires an independently retained lowercase exact SHA-256")
    return value


def run(cmd, timeout=25):
    try:
        p = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL,
                           timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReviewDenied("required offline Ed25519 operation unavailable") from exc
    if p.returncode:
        deny("offline Ed25519 key/signature operation was rejected")
    if len(p.stdout) > 8192:
        deny("key inspection output exceeded bound")
    return p.stdout


def read(path, limit=65536):
    if not isinstance(path, Path) or not path.is_absolute() or path.is_symlink():
        deny("signed evidence requires absolute, non-symlink files")
    st = path.lstat()
    if (not path.is_file() or st.st_nlink != 1 or st.st_size <= 0
            or st.st_size > limit):
        deny("signed evidence file is not bounded regular single-link data")
    raw = path.read_bytes()
    if len(raw) != st.st_size:
        deny("signed evidence changed while read")
    return raw


def decode(raw):
    def unique(pairs):
        result = {}
        for name, value in pairs:
            if name in result:
                deny("duplicate object key in signed JSON")
            result[name] = value
        return result
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                         parse_constant=lambda unused: deny("nonfinite JSON"))
    except (UnicodeError, ValueError) as exc:
        raise ReviewDenied("malformed signed JSON") from exc
    if manifest.canonical(obj) != raw:
        deny("signed evidence must be unique canonical JSON")
    return obj


def public_der(args):
    pem = read(args.public_key, 32768)
    if b"PRIVATE KEY" in pem or b"BEGIN PUBLIC KEY" not in pem:
        deny("only a separately provided public key may be trusted")
    der = run(["openssl", "pkey", "-pubin", "-inform", "PEM",
               "-in", str(args.public_key), "-outform", "DER"])
    if sha(der) != pinned(args.public_key_der_sha256, "reviewer public key DER"):
        deny("public key does not match externally pinned exact DER")
    if not der.startswith(bytes.fromhex("302a300506032b6570032100")) or len(der) != 44:
        deny("only Ed25519 public keys are permitted")
    return der


def signed_bytes(body):
    return DOMAIN + len(manifest.canonical(body)).to_bytes(8, "big") + manifest.canonical(body)


def openssl_signature(mode, keyfile, signed_data, sig=None):
    # Operator's key is NEVER copied into Git, a Docker layer or artifact.
    with tempfile.TemporaryDirectory(prefix="nexus-stage241-ed25519-") as tmp:
        root = Path(tmp)
        msg = root / "message.bin"
        msg.write_bytes(signed_data)
        os.chmod(msg, 0o600)
        signature = root / "signature.bin"
        if mode == "sign":
            command = ["openssl", "pkeyutl", "-sign", "-rawin",
                       "-inkey", str(keyfile), "-in", str(msg),
                       "-out", str(signature)]
            run(command)
            return signature.read_bytes()
        signature.write_bytes(sig)
        os.chmod(signature, 0o600)
        command = ["openssl", "pkeyutl", "-verify", "-rawin", "-pubin",
                   "-inkey", str(keyfile), "-in", str(msg),
                   "-sigfile", str(signature)]
        run(command)
        return None


def manifest_inputs(args):
    pinned(args.expected_manifest_sha256, "manifest")
    pin_sbom = pinned(args.expected_sbom_sha256, "partial SBOM")
    verified = manifest.verify(argparse.Namespace(
        evidence=args.manifest, sbom=args.sbom,
        expected_sha256=args.expected_manifest_sha256,
        commit=args.reviewed_commit, image=None,
    ))
    if sha(read(args.sbom, manifest.MAX)) != pin_sbom:
        deny("partial SBOM differs from independently approved checksum")
    doc = decode(read(args.manifest, manifest.MAX))
    if (doc["local_oci_image_id"] != args.local_image_id
            or doc["release_authorized"] is not False
            or doc["registry_digest_attested"] is not False
            or doc["signed_provenance_attested"] is not False):
        deny("unreviewed image identity or claimed release/provenance")
    if verified["release_gate"] != "BLOCKED":
        deny("Stage 240 manifest has unexpected release gate")
    return doc


def expected_body(args):
    doc = manifest_inputs(args)
    if not isinstance(args.reviewer_key_id, str) or not KEY_ID.fullmatch(args.reviewer_key_id):
        deny("invalid reviewer key identity")
    return {
        "schema": SCHEMA, "algorithm": "Ed25519",
        "reviewer_key_id": args.reviewer_key_id,
        "scope": "synthetic-offline-review-only",
        "reviewed_pr_commit": doc["reviewed_pr_commit"],
        "evidence_manifest_sha256": args.expected_manifest_sha256,
        "sbom_sha256": args.expected_sbom_sha256,
        "local_image_id": doc["local_oci_image_id"],
        "published_registry_digest": None,
        "independent_builder_provenance_verified": False,
        "production_release_authorized": False,
    }


def sign(args):
    public_der(args)
    if (args.private_key is None or not args.private_key.is_absolute()
            or args.private_key.is_symlink()):
        deny("operator-private Ed25519 signing key path required")
    st = args.private_key.stat()
    if st.st_nlink != 1 or st.st_mode & 0o077 or st.st_uid != os.geteuid():
        deny("operator private signing key must be owner-only")
    body = expected_body(args)
    sig = openssl_signature("sign", args.private_key, signed_bytes(body))
    if len(sig) != 64:
        deny("invalid Ed25519 signature size")
    openssl_signature("verify", args.public_key, signed_bytes(body), sig)
    result = dict(body, signature_base64=base64.b64encode(sig).decode())
    encoded = manifest.canonical(result)
    # Exclusive creation + fsync; a reissued signed review cannot silently
    # replace a previously independently pinned report.
    flags = os.O_WRONLY | os.O_EXCL | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(args.signed_review, flags, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(encoded)
        out.flush()
        os.fsync(out.fileno())
    return {"status": "SYNTHETIC_REVIEW_SIGNED_NOT_DEPLOYABLE",
            "signed_review_sha256": sha(encoded),
            "release_gate": "BLOCKED",
            "production_release_authorized": False}


def verify(args):
    public_der(args)
    body = expected_body(args)
    raw = read(args.signed_review)
    if sha(raw) != pinned(args.expected_signed_sha256, "signed review"):
        deny("signed review differs from separately pinned exact bytes")
    d = decode(raw)
    if not isinstance(d, dict) or set(d) != SIGNED_FIELDS:
        deny("review has unknown signature or authority fields")
    if {key: d[key] for key in BODY_FIELDS} != body:
        deny("signed review does not bind approved image, reviewer and evidence")
    sig64 = d["signature_base64"]
    if not isinstance(sig64, str):
        deny("signature must be a strict canonical base64 string")
    try:
        signature = base64.b64decode(sig64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ReviewDenied("invalid base64 signature") from exc
    if len(signature) != 64 or base64.b64encode(signature).decode() != sig64:
        deny("invalid canonical Ed25519 signature length")
    openssl_signature("verify", args.public_key, signed_bytes(body), signature)
    return {
        "status": "SIGNED_SYNTHETIC_REVIEW_VERIFIED_NOT_DEPLOYABLE",
        "signed_review_sha256": args.expected_signed_sha256,
        "reviewer_public_key_der_sha256": args.public_key_der_sha256,
        "manifest_sha256": args.expected_manifest_sha256,
        "sbom_sha256": args.expected_sbom_sha256,
        "release_gate": "BLOCKED",
        "production_release_authorized": False,
    }


def admission(args):
    reviewed = verify(args)
    raw = read(args.deployment_intent)
    if sha(raw) != pinned(args.expected_intent_sha256, "deployment intent"):
        deny("deployment intent differs from independently pinned bytes")
    doc = decode(raw)
    if not isinstance(doc, dict) or set(doc) != PLAN_FIELDS:
        deny("unknown deployment admission policy")
    expected = {
        "schema": PLAN_SCHEMA,
        "scope": "synthetic-only",
        "reviewed_pr_commit": args.reviewed_commit,
        "evidence_manifest_sha256": args.expected_manifest_sha256,
        "local_image_id": args.local_image_id,
        "requested_registry_digest": None,
        "network_policy": "isolated-loopback-only",
        "data_policy": "new-disposable-synthetic-volume",
        "container_user": "10001:10001",
        "expected_entrypoint": ENTRY,
        "entrypoint_override_allowed": False,
        "privileged_allowed": False,
        "privilege_escalation_allowed": False,
        "host_paths_allowed": False,
        "production_credentials_allowed": False,
        "live_provider_allowed": False,
        "deployment_authorized": False,
    }
    if doc != expected:
        deny("deployment intent differs from approved synthetic-only fail-closed policy")
    return dict(reviewed, status="SYNTHETIC_INTENT_CONSISTENT_NOT_DEPLOYABLE",
                deployment_intent_sha256=args.expected_intent_sha256,
                real_orchestrator_policy_installed=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("sign-synthetic", "verify", "inspect-intent", "admission-gate"))
    for field in ("manifest", "sbom", "public-key", "signed-review", "private-key",
                  "deployment-intent"):
        p.add_argument("--" + field, type=Path)
    for field in ("reviewed-commit", "expected-manifest-sha256",
                  "expected-sbom-sha256", "local-image-id", "reviewer-key-id",
                  "public-key-der-sha256", "expected-signed-sha256",
                  "expected-intent-sha256"):
        p.add_argument("--" + field)
    args = p.parse_args()
    try:
        required = [
            args.manifest, args.sbom, args.public_key, args.signed_review,
            args.reviewed_commit, args.expected_manifest_sha256,
            args.expected_sbom_sha256, args.local_image_id,
            args.reviewer_key_id, args.public_key_der_sha256,
        ]
        if any(x is None for x in required):
            deny("exact manifest/SBOM, signer, image and all independent pins required")
        if args.mode == "sign-synthetic":
            result = sign(args)
        elif args.mode == "verify":
            result = verify(args)
        else:
            if args.deployment_intent is None or args.expected_intent_sha256 is None:
                deny("explicit independently pinned deployment intent required")
            result = admission(args)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        if args.mode == "admission-gate":
            print("NEXUS STAGE D ADMISSION: BLOCKED; no real image digest/independent policy", file=sys.stderr)
            return 1
        return 0
    except (ReviewDenied, manifest.Denied, OSError, KeyError, TypeError,
            ValueError, UnicodeError) as exc:
        print("NEXUS STAGE D SIGNED REVIEW DENIED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
