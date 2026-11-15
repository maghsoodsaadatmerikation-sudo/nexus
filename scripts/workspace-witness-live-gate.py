#!/usr/bin/env python3
"""Fail-closed online witness comparison against an independently pinned receipt.

This is an *evidence-only* protocol probe; it NEVER approves deployment,
trusts an offsite custodian's organizational independence, grants import
authority, writes the NEXUS trust ledger or changes a remote receipt.
"""

import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "nexus_live_witness_client", HERE / "workspace-witness-ssh-client.py"
)
if spec is None or spec.loader is None:
    raise RuntimeError("pinned SSH witness client unavailable")
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)
trust = client.trust

REPORT_SCHEMA = "nexus.witness.live-protocol-evidence.v1"
HEX_SHA = re.compile(r"[0-9a-f]{64}\Z")


class ReadinessError(Exception):
    pass


def deny(message):
    raise ReadinessError(message)


def run(args):
    if not HEX_SHA.fullmatch(args.trusted_package_sha256):
        deny("independent exact-checkpoint SHA-256 must be supplied")
    if args.minimum_sequence < 1:
        deny("positive independently retained sequence floor is required")

    # The local mutable trust registry cannot authenticate itself as an
    # independently retained latest receipt. The external checkpoint and
    # the resulting evidence file must stay outside that directory.
    state = args.state_dir.resolve()
    if (args.trusted_package.resolve().is_relative_to(state)
            or args.report.resolve().is_relative_to(state)):
        deny("independent checkpoint and evidence file must be outside local trust directory")
    if args.trusted_package.resolve() == args.report.resolve():
        deny("evidence must never overwrite an independent checkpoint")
    if not args.report.is_absolute() or args.report.exists() or args.report.is_symlink():
        deny("evidence destination must be a new explicit absolute path")
    if not args.trusted_package.is_absolute():
        deny("independent package must use an absolute path")

    client.custodian.secure_inputs(
        args.source_public_key, args.ack_public_key,
        args.source_key_id, args.ack_key_id
    )
    trust.valid_key_id(args.receiver_id)
    # Verify and fingerprint explicitly pinned host material *before* SSH.
    known_hosts = client.checked_file(args.known_hosts)
    client.checked_file(args.identity, private=True)

    raw = trust.open_no_symlinks(args.trusted_package, client.MAX_PACKAGE)
    if hashlib.sha256(raw).hexdigest() != args.trusted_package_sha256:
        deny("externally retained checkpoint bytes differ from independently supplied digest")
    expected = trust.strict_json(raw)
    # Both source and receiver Ed25519 signatures and current operator state
    # must agree with independently pinned keys and minimum sequence.
    client.verify_package(expected, args)

    # Only a read-only latest request is sent. No signer key, user data,
    # Workspace, or new receipt is sent to the receiver.
    remote = client.exchange(args, "latest")
    client.verify_package(remote, args)
    if remote != expected:
        deny("live SSH receiver latest differs from independently retained checkpoint")
    ack = remote["ack"]
    receipt = remote["receipt"]
    if ack["sequence"] < args.minimum_sequence:
        deny("receiver sequence is older than independently retained floor")

    checks = [
        "pinned_ssh_host_key",
        "separate_ed25519_source_and_recipient_keys",
        "source_receipt_signature",
        "recipient_acknowledgment_signature",
        "minimum_independent_sequence",
        "exact_independent_latest_package",
        "current_local_trust_commitment",
    ]
    report = {
        "schema": REPORT_SCHEMA,
        "result": "cryptographic_protocol_match",
        "receiver_id": args.receiver_id,
        "source_key_id": args.source_key_id,
        "ack_key_id": args.ack_key_id,
        "ack_sequence": ack["sequence"],
        "receipt_sha256": client.custodian.digest(receipt),
        "ack_sha256": client.custodian.digest(ack),
        "state_sha256": receipt["state_sha256"],
        "independently_supplied_package_sha256": args.trusted_package_sha256,
        "pinned_known_hosts_sha256": hashlib.sha256(
            trust.open_no_symlinks(known_hosts, 8192)
        ).hexdigest(),
        "verified_checks": checks,
        "external_administrative_independence": "not_verified",
        "immutable_retention": "not_verified",
        "production_deployment": "not_verified",
        "machine_history_import_authorized": False,
    }
    # Treat this as an unsigned observation, not an attestation authority.
    client.write_package(args.report, report)
    print(
        "NEXUS LIVE WITNESS PROTOCOL MATCH: independently pinned receipt="
        + args.trusted_package_sha256
        + ", sequence=" + str(ack["sequence"])
        + "; external administrative independence, WORM custody and "
          "production deployment NOT VERIFIED"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--known-hosts", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--receiver-id", required=True)
    parser.add_argument("--source-key-id", required=True)
    parser.add_argument("--source-public-key", type=Path, required=True)
    parser.add_argument("--ack-key-id", required=True)
    parser.add_argument("--ack-public-key", type=Path, required=True)
    parser.add_argument("--minimum-sequence", type=int, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--trusted-package", type=Path, required=True)
    parser.add_argument("--trusted-package-sha256", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        run(args)
    except (ReadinessError, client.TransportError,
            client.custodian.CustodianError, client.custodian.witness.WitnessError,
            trust.TrustError, OSError, ValueError, TypeError) as exc:
        print("NEXUS LIVE WITNESS PROBE DENIED: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
