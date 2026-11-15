#!/usr/bin/env python3
"""Offline role-separated signed observations of two staged v2 history copies.

This verifies two independent Ed25519 *keys*, not two physical hosts.
It never grants deployment, keys, import, or independent-custody authority.
"""
import argparse
import base64
import binascii
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "nexus_two_observers_stager", HERE / "workspace-witness-v2-stager.py")
if spec is None or spec.loader is None:
    raise RuntimeError("v2 stage verification unavailable")
stager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stager)
v2 = stager.v2
trust = stager.trust
SCHEMA = "nexus.offsite.two-custody-observation.v1"
DOMAIN = b"NEXUS\x00two-custody-observation\x00Ed25519\x00v1\x00"
ROLES = ("origin", "recovery")
CHALLENGE = re.compile(r"[a-f0-9]{64}\Z")
FIELDS = {
    "schema", "role", "observer_id", "observer_public_sha256",
    "challenge_hex", "old_ledger_sha256", "consent_sha256",
    "bridge_sha256", "trusted_latest_package_sha256",
    "old_sequence", "latest_sequence", "latest_ack_sha256", "signature_base64",
}
BODY_FIELDS = FIELDS - {"signature_base64"}
MAX_REPORT_BYTES = 4096


class ObservationError(Exception):
    pass


def fail(message):
    raise ObservationError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def challenge(value):
    if not isinstance(value, str) or not CHALLENGE.fullmatch(value):
        fail("a separately approved 32-byte hexadecimal one-use challenge is required")
    if value == "0" * 64:
        fail("all-zero challenge is not an acceptable operator challenge")
    return value


def observer_keys(args):
    observer_id = v2.custodian.key_id(args.observer_id)
    pub_der = trust.derive_ed25519_public_der(args.observer_public_key)
    source_der, outgoing_der = v2.custodian.secure_inputs(
        args.source_public_key, args.outgoing_ack_public_key,
        args.source_key_id, args.outgoing_ack_key_id)
    incoming_der = trust.derive_ed25519_public_der(args.incoming_ack_public_key)
    if pub_der in (source_der, outgoing_der, incoming_der):
        fail("observer must not reuse source, old receiver or new receiver signer")
    return observer_id, pub_der


def preimage(body):
    raw = trust.encode_json(body)
    return DOMAIN + len(raw).to_bytes(8, "big") + raw


def proof_args(args, bridge_path):
    return argparse.Namespace(
        old_ledger=args.old_ledger,
        old_ledger_sha256=args.old_ledger_sha256,
        trusted_old_package=args.trusted_old_package,
        trusted_old_package_sha256=args.trusted_old_package_sha256,
        consent=args.consent,
        consent_sha256=args.consent_sha256,
        bridge=bridge_path,
        bridge_sha256=args.expected_bridge_sha256,
        trusted_new_package=args.trusted_latest_package,
        trusted_new_package_sha256=args.trusted_latest_package_sha256,
        receiver_id=args.receiver_id,
        source_key_id=args.source_key_id,
        source_public_key=args.source_public_key,
        outgoing_ack_key_id=args.outgoing_ack_key_id,
        outgoing_ack_public_key=args.outgoing_ack_public_key,
        incoming_ack_key_id=args.incoming_ack_key_id,
        incoming_ack_public_key=args.incoming_ack_public_key,
        minimum_sequence=args.minimum_sequence,
    )


def observation_body(args, role, observer_id, pub_der, proof):
    return {
        "schema": SCHEMA,
        "role": role,
        "observer_id": observer_id,
        "observer_public_sha256": sha(pub_der),
        "challenge_hex": challenge(args.challenge_hex),
        "old_ledger_sha256": args.old_ledger_sha256,
        "consent_sha256": args.consent_sha256,
        "bridge_sha256": args.expected_bridge_sha256,
        "trusted_latest_package_sha256": args.trusted_latest_package_sha256,
        "old_sequence": proof["old_sequence"],
        "latest_sequence": proof["new_sequence"],
        "latest_ack_sha256": proof["new_last_ack_sha256"],
    }


def sign_observation(args):
    if args.role not in ROLES:
        fail("unrecognized observer role")
    observer_id, pub_der = observer_keys(args)
    if v2.custodian.witness.private_signer(args.observer_private_key) != pub_der:
        fail("private witness identity differs from independently trusted observer public key")
    challenge(args.challenge_hex)
    if not args.store.is_absolute():
        fail("observation requires an explicit absolute private stage path")
    fd = trust.protected_directory(args.store)
    try:
        stager.assert_directory_identity(args.store, fd)
        raw = stager.read_locked(fd)
        if sha(raw) != args.expected_bridge_sha256:
            fail("observed staging head does not match independent exact hash")
        # Use the actual on-disk verified canonical candidate, not a
        # user-generated status string or untrusted claimed sequence.
        candidate = args.store / stager.FILE
        proof = v2.verify(proof_args(args, candidate))
        stager.assert_directory_identity(args.store, fd)
        if stager.read_locked(fd) != raw:
            fail("stage changed during observation")
    finally:
        import os
        os.close(fd)
    body = observation_body(args, args.role, observer_id, pub_der, proof)
    signature = trust.attestation.openssl(
        "sign", args.observer_private_key, preimage(body))
    if len(signature) != 64:
        fail("invalid Ed25519 observation signature size")
    output = {**body, "signature_base64": base64.b64encode(signature).decode("ascii")}
    v2.custodian.witness.write_exclusive(args.output, output)
    return {"status": "signed-one-offline-observation",
            "role": args.role, "observer_id": observer_id,
            "report_sha256": sha(trust.encode_json(output)),
            "production_release_authorized": False,
            "physical_host_independence_proven": False}


def verify_report(args, role, report_path, report_sha, pub_path, observer_id, proof):
    if not isinstance(report_sha, str) or not v2.HEX.fullmatch(report_sha):
        fail("independent exact signed observation SHA-256 pin is required")
    raw = trust.open_no_symlinks(report_path, MAX_REPORT_BYTES)
    if sha(raw) != report_sha:
        fail("signed observer report changed against independent exact pin")
    report = trust.strict_json(raw)
    if trust.encode_json(report) != raw:
        fail("observer report is not canonically encoded")
    if not isinstance(report, dict) or set(report) != FIELDS:
        fail("malformed signed observer report")
    key = v2.custodian.key_id(observer_id)
    pub_der = trust.derive_ed25519_public_der(pub_path)
    body = observation_body(args, role, key, pub_der, proof)
    if any(report.get(k) != v for k, v in body.items()):
        fail("signed report differs from approved challenge, signer or v2 history")
    signature = report["signature_base64"]
    if not isinstance(signature, str):
        fail("missing Ed25519 observer signature")
    try:
        sig = base64.b64decode(signature, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ObservationError("malformed detached signature") from exc
    if len(sig) != 64 or base64.b64encode(sig).decode("ascii") != signature:
        fail("noncanonical detached signature")
    with v2.tempfile.TemporaryDirectory(prefix="nexus-observer-key-") as folder:
        pub = Path(folder) / "observer.pub.pem"
        pub.write_bytes(v2.custodian.public_from_der(pub_der))
        try:
            trust.attestation.openssl("verify", pub, preimage(body), sig)
        except trust.attestation.AttestationError as exc:
            raise ObservationError("observer signature does not verify") from exc
    return pub_der


def verify_pair(args):
    challenge(args.challenge_hex)
    if args.origin_observer_id == args.recovery_observer_id:
        fail("observer signer IDs must be different")
    origin_pub = trust.derive_ed25519_public_der(args.origin_public_key)
    recovery_pub = trust.derive_ed25519_public_der(args.recovery_public_key)
    if origin_pub == recovery_pub:
        fail("same observer public key may not attest to both roles")
    signer_der = (
        trust.derive_ed25519_public_der(args.source_public_key),
        trust.derive_ed25519_public_der(args.outgoing_ack_public_key),
        trust.derive_ed25519_public_der(args.incoming_ack_public_key),
    )
    if origin_pub in signer_der or recovery_pub in signer_der:
        fail("observer signers must be separate from the ledger's source and receiver keys")
    if not args.approved_bridge.is_absolute():
        fail("approved bridge must be an explicitly selected absolute path")
    proof = v2.verify(proof_args(args, args.approved_bridge))
    seen_origin = verify_report(
        args, "origin", args.origin_report, args.origin_report_sha256,
        args.origin_public_key, args.origin_observer_id, proof)
    seen_recovery = verify_report(
        args, "recovery", args.recovery_report, args.recovery_report_sha256,
        args.recovery_public_key, args.recovery_observer_id, proof)
    if seen_origin == seen_recovery:
        fail("both observations signed by one key")
    return {
        "schema": "nexus.offsite.two-custody-observation-result.v1",
        "status": "two-distinct-signer-observations-verified",
        "bridge_sha256": args.expected_bridge_sha256,
        "latest_sequence": proof["new_sequence"],
        "latest_ack_sha256": proof["new_last_ack_sha256"],
        "challenge_hex": args.challenge_hex,
        "distinct_signer_public_keys_verified": True,
        "physical_host_independence_proven": False,
        "real_offsite_restore_performed": False,
        "production_release_authorized": False,
    }


def common(p):
    for flag in ("old-ledger", "trusted-old-package", "consent",
                 "source-public-key", "outgoing-ack-public-key",
                 "incoming-ack-public-key", "trusted-latest-package"):
        p.add_argument("--" + flag, type=Path, required=True)
    for flag in ("old-ledger-sha256", "trusted-old-package-sha256",
                 "consent-sha256", "receiver-id", "source-key-id",
                 "outgoing-ack-key-id", "incoming-ack-key-id",
                 "trusted-latest-package-sha256", "expected-bridge-sha256",
                 "challenge-hex"):
        p.add_argument("--" + flag, required=True)
    p.add_argument("--minimum-sequence", type=int, required=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    actions = p.add_subparsers(dest="mode", required=True)
    observe = actions.add_parser("observe")
    inspect = actions.add_parser("verify-pair")
    for mode in (observe, inspect):
        common(mode)
    for flag in ("store", "observer-private-key", "observer-public-key", "output"):
        observe.add_argument("--" + flag, type=Path, required=True)
    observe.add_argument("--observer-id", required=True)
    observe.add_argument("--role", choices=ROLES, required=True)
    inspect.add_argument("--approved-bridge", type=Path, required=True)
    for flag in ("origin-report", "recovery-report", "origin-public-key",
                 "recovery-public-key"):
        inspect.add_argument("--" + flag, type=Path, required=True)
    for flag in ("origin-report-sha256", "recovery-report-sha256",
                 "origin-observer-id", "recovery-observer-id"):
        inspect.add_argument("--" + flag, required=True)
    args = p.parse_args()
    try:
        result = sign_observation(args) if args.mode == "observe" else verify_pair(args)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (ObservationError, stager.StageError, v2.EpochError,
            v2.transition.ConsentError, v2.custodian.CustodianError,
            v2.custodian.witness.WitnessError, trust.TrustError,
            OSError, TypeError, ValueError, KeyError) as exc:
        print("NEXUS INDEPENDENT OBSERVER EVIDENCE DENIED: " + str(exc),
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
