#!/usr/bin/env python3
"""Offline verification-only v1 -> v2 custodian signing-key epoch bridge.

Validates historical v1 signed receipts, the three-party transition consent,
and an append-only, domain-separated v2 acknowledgment sequence signed by
the approved incoming key. It does NOT activate the key or write a ledger.
"""
import argparse
import base64
import binascii
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import tempfile

HERE = Path(__file__).resolve().parent


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError("required NEXUS verifier unavailable")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


custodian = module("nexus_v2_custodian", "workspace-witness-custodian.py")
transition = module("nexus_v2_transition", "workspace-witness-key-transition.py")
trust = custodian.trust

SCHEMA = "nexus.offsite.receiver-key-epoch-bridge.v2"
ACK_SCHEMA = "nexus.offsite.custodian-ack.v2"
PACKAGE_SCHEMA = "nexus.offsite.receiver-key-epoch-package.v2"
DOMAIN = b"NEXUS\x00offsite-custodian-receipt-ack\x00Ed25519\x00v2\x00"
HEX = re.compile(r"[0-9a-f]{64}\Z")
MAX_BRIDGE_BYTES = 512 * 1024
MAX_V2_ENTRIES = 64
ACK_FIELDS = {
    "schema", "algorithm", "receiver_id", "sequence", "epoch",
    "source_key_id", "ack_key_id", "source_receipt_sha256", "state_sha256",
    "previous_ack_sha256", "transition_proposal_sha256", "signature_base64",
}
BODY_FIELDS = ACK_FIELDS - {"signature_base64"}
BRIDGE_FIELDS = {
    "schema", "old_ledger_sha256", "consent_sha256",
    "transition_proposal_sha256", "entries",
}


class EpochError(Exception):
    pass


def fail(message):
    raise EpochError(message)


def pinned(path, exact_sha, label, max_bytes):
    if not isinstance(exact_sha, str) or not HEX.fullmatch(exact_sha):
        fail("independently approved " + label + " SHA-256 is required")
    raw = trust.open_no_symlinks(path, max_bytes)
    if hashlib.sha256(raw).hexdigest() != exact_sha:
        fail(label + " differs from approved exact file bytes")
    return trust.strict_json(raw)


def preimage(body):
    data = trust.encode_json(body)
    return DOMAIN + len(data).to_bytes(8, "big") + data


def validate_ack(ack, receipt, *, receiver, source_id, incoming_id,
                 sequence, previous, proposal_hash, incoming_pub):
    if not isinstance(ack, dict) or set(ack) != ACK_FIELDS:
        fail("unexpected or missing v2 acknowledgment fields")
    if (ack["schema"] != ACK_SCHEMA or ack["algorithm"] != "Ed25519"
            or ack["receiver_id"] != receiver
            or type(ack["sequence"]) is not int or ack["sequence"] != sequence
            or type(ack["epoch"]) is not int or ack["epoch"] != 2
            or ack["source_key_id"] != source_id
            or ack["ack_key_id"] != incoming_id
            or ack["source_receipt_sha256"] != custodian.digest(receipt)
            or ack["state_sha256"] != receipt["state_sha256"]
            or ack["previous_ack_sha256"] != previous
            or ack["transition_proposal_sha256"] != proposal_hash):
        fail("v2 acknowledgment does not cryptographically extend approved history")
    encoded = ack["signature_base64"]
    if not isinstance(encoded, str):
        fail("missing v2 detached signature")
    try:
        signature = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise EpochError("malformed v2 signature") from exc
    if len(signature) != 64 or base64.b64encode(signature).decode("ascii") != encoded:
        fail("noncanonical v2 signature")
    body = {key: ack[key] for key in BODY_FIELDS}
    try:
        trust.attestation.openssl("verify", incoming_pub, preimage(body), signature)
    except trust.attestation.AttestationError as exc:
        raise EpochError("incoming-key v2 signature rejected") from exc


def verify(args):
    receiver = custodian.key_id(args.receiver_id)
    source_id = custodian.key_id(args.source_key_id)
    old_id = custodian.key_id(args.outgoing_ack_key_id)
    incoming_id = custodian.key_id(args.incoming_ack_key_id)
    source_der, old_der = custodian.secure_inputs(
        args.source_public_key, args.outgoing_ack_public_key, source_id, old_id)
    incoming_der = trust.derive_ed25519_public_der(args.incoming_ack_public_key)
    if (incoming_id in (source_id, old_id)
            or incoming_der in (source_der, old_der)):
        fail("new epoch signer must be a distinct cryptographic identity")

    original = pinned(args.old_ledger, args.old_ledger_sha256,
                      "old v1 ledger", custodian.MAX_STORE_BYTES)
    custodian.inspect_store(original)  # authenticate ALL historical v1 entries
    if (original["receiver_id"] != receiver
            or original["source_key_id"] != source_id
            or original["ack_key_id"] != old_id
            or custodian.derived_keys(original) != (source_der, old_der)):
        fail("old historical ledger differs from independently pinned identities")
    old_entries = original["entries"]
    if not old_entries:
        fail("cannot rotate an unacknowledged empty v1 ledger")

    old_package = pinned(
        args.trusted_old_package, args.trusted_old_package_sha256,
        "independent old latest checkpoint", custodian.MAX_PACKAGE_BYTES)
    if old_package != {"schema": custodian.PACKAGE_SCHEMA, **old_entries[-1]}:
        fail("old latest signed checkpoint does not equal old historical ledger")

    # Consent verifies three role-separated Ed25519 approvals, exact source
    # and outgoing/new keys, and the externally retained old checkpoint.
    approval = pinned(args.consent, args.consent_sha256,
                      "three-party consent", transition.MAX_CONSENT_BYTES)
    if (not isinstance(approval, dict)
            or set(approval) != {"schema", "proposal", "approvals"}):
        fail("malformed approved consent document")
    consent_args = argparse.Namespace(
        receiver_id=receiver, source_key_id=source_id,
        source_public_key=args.source_public_key,
        outgoing_ack_key_id=old_id,
        outgoing_ack_public_key=args.outgoing_ack_public_key,
        incoming_ack_key_id=incoming_id,
        incoming_ack_public_key=args.incoming_ack_public_key,
        trusted_latest_package=args.trusted_old_package,
        trusted_package_sha256=args.trusted_old_package_sha256,
        minimum_sequence=len(old_entries), input=args.consent)
    with contextlib.redirect_stdout(io.StringIO()):
        transition.verify(consent_args)
    proposal_hash = hashlib.sha256(
        trust.encode_json(approval["proposal"])).hexdigest()

    bridge = pinned(args.bridge, args.bridge_sha256,
                    "v2 transition candidate", MAX_BRIDGE_BYTES)
    if (not isinstance(bridge, dict) or set(bridge) != BRIDGE_FIELDS
            or bridge["schema"] != SCHEMA
            or bridge["old_ledger_sha256"] != args.old_ledger_sha256
            or bridge["consent_sha256"] != args.consent_sha256
            or bridge["transition_proposal_sha256"] != proposal_hash):
        fail("v2 bridge not bound to exact old ledger and approved proposal")
    entries = bridge["entries"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_V2_ENTRIES:
        fail("candidate needs 1-64 v2 acknowledgments, not empty/unbounded list")
    if (type(args.minimum_sequence) is not int
            or args.minimum_sequence < len(old_entries)
            or args.minimum_sequence > len(old_entries) + len(entries)):
        fail("independent minimum sequence is outside verified candidate history")

    seen_receipts = {custodian.digest(x["receipt"]) for x in old_entries}
    seen_states = {x["receipt"]["state_sha256"] for x in old_entries}
    previous = custodian.digest(old_entries[-1]["ack"])
    with tempfile.TemporaryDirectory(prefix="nexus-v2-verify-") as directory:
        source_pub = Path(directory) / "source.pem"
        incoming_pub = Path(directory) / "new-ack.pem"
        source_pub.write_bytes(custodian.public_from_der(source_der))
        incoming_pub.write_bytes(custodian.public_from_der(incoming_der))
        for number, entry in enumerate(entries, start=len(old_entries) + 1):
            if not isinstance(entry, dict) or set(entry) != {"receipt", "ack"}:
                fail("unrecognized v2 receipt-and-acknowledgment entry")
            receipt = entry["receipt"]
            custodian.validated_receipt(receipt, source_pub, source_id)
            receipt_sha = custodian.digest(receipt)
            state_sha = receipt["state_sha256"]
            if receipt_sha in seen_receipts or state_sha in seen_states:
                fail("v2 repeats already acknowledged source receipt/state")
            validate_ack(
                entry["ack"], receipt, receiver=receiver, source_id=source_id,
                incoming_id=incoming_id, sequence=number, previous=previous,
                proposal_hash=proposal_hash, incoming_pub=incoming_pub)
            previous = custodian.digest(entry["ack"])
            seen_receipts.add(receipt_sha)
            seen_states.add(state_sha)

    latest = pinned(args.trusted_new_package, args.trusted_new_package_sha256,
                    "independent new latest signed checkpoint",
                    custodian.MAX_PACKAGE_BYTES)
    if (not isinstance(latest, dict)
            or set(latest) != {"schema", "receipt", "ack"}
            or latest != {"schema": PACKAGE_SCHEMA, **entries[-1]}):
        fail("new latest independently retained package does not match v2 tail")
    return {
        "schema": "nexus.offsite.key-epoch-verification.v2",
        "status": "verified-offline-key-epoch-bridge",
        "old_sequence": len(old_entries),
        "new_sequence": len(old_entries) + len(entries),
        "new_key_id": incoming_id,
        "old_last_ack_sha256": custodian.digest(old_entries[-1]["ack"]),
        "new_last_ack_sha256": previous,
        "approved_proposal_sha256": proposal_hash,
        "historical_v1_signatures_preserved": True,
        "production_cutover_authorized": False,
        "independent_custody_proven": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ("old-ledger", "trusted-old-package", "consent", "bridge",
                 "trusted-new-package", "source-public-key",
                 "outgoing-ack-public-key", "incoming-ack-public-key"):
        p.add_argument("--" + flag, type=Path, required=True)
    for flag in ("old-ledger-sha256", "trusted-old-package-sha256",
                 "consent-sha256", "bridge-sha256", "trusted-new-package-sha256",
                 "receiver-id", "source-key-id",
                 "outgoing-ack-key-id", "incoming-ack-key-id"):
        p.add_argument("--" + flag, required=True)
    p.add_argument("--minimum-sequence", type=int, required=True)
    args = p.parse_args()
    try:
        print(json.dumps(verify(args), separators=(",", ":"), sort_keys=True))
        return 0
    except (EpochError, transition.ConsentError, custodian.CustodianError,
            custodian.witness.WitnessError, trust.TrustError,
            OSError, ValueError, TypeError, KeyError) as exc:
        print("NEXUS V2 KEY EPOCH VERIFICATION DENIED: " + str(exc),
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
