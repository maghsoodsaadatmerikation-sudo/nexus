#!/usr/bin/env python3
"""Read-only prefix proof for independently transported v1 witness ledgers.

This is a signed-history consistency check, NOT evidence that two files have
different owners or that a receiver is independent. No keys, stores, network,
runtime authority, or machine history are modified.
"""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "nexus_prefix_custodian", HERE / "workspace-witness-custodian.py")
if spec is None or spec.loader is None:
    raise RuntimeError("witness custodian verifier unavailable")
custodian = importlib.util.module_from_spec(spec)
spec.loader.exec_module(custodian)
trust = custodian.trust
SCHEMA = "nexus.offsite.ledger-prefix-proof.v1"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class PrefixError(Exception):
    pass


def fail(reason):
    raise PrefixError(reason)


def pinned_sha(value, name):
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        fail("independent " + name + " SHA-256 pin must be 64 lowercase hex characters")
    return value


def strict_pinned(path, approved_hash, name, max_bytes):
    raw = trust.open_no_symlinks(path, max_bytes)
    if hashlib.sha256(raw).hexdigest() != pinned_sha(approved_hash, name):
        fail(name + " differs from the independently approved exact bytes")
    return trust.strict_json(raw), hashlib.sha256(raw).hexdigest()


def trusted_identity(store, args, source_der, ack_der):
    if (store["receiver_id"] != args.receiver_id
            or store["source_key_id"] != args.source_key_id
            or store["ack_key_id"] != args.ack_key_id):
        fail("receiver or source/ack signer ID mismatch")
    stored_source, stored_ack = custodian.derived_keys(store)
    if stored_source != source_der or stored_ack != ack_der:
        fail("receiver signer keys differ from independently pinned public keys")


def prove(args):
    custodian.key_id(args.receiver_id)
    source_der, ack_der = custodian.secure_inputs(
        args.source_public_key, args.ack_public_key,
        args.source_key_id, args.ack_key_id)
    original, original_sha = strict_pinned(
        args.baseline_ledger, args.baseline_sha256, "baseline ledger",
        custodian.MAX_STORE_BYTES)
    successor, successor_sha = strict_pinned(
        args.candidate_ledger, args.candidate_sha256, "candidate ledger",
        custodian.MAX_STORE_BYTES)
    # Inspect *every* historical receipt and Ed25519 acknowledgment, not
    # merely the last signed acknowledgment or a numeric sequence.
    custodian.inspect_store(original)
    custodian.inspect_store(successor)
    trusted_identity(original, args, source_der, ack_der)
    trusted_identity(successor, args, source_der, ack_der)
    old = original["entries"]
    new = successor["entries"]
    if not old or len(new) <= len(old):
        fail("candidate is empty, rolled back, or has no new acknowledgment")
    if (args.minimum_sequence < len(old)
            or args.minimum_sequence > len(new)
            or args.minimum_sequence < 1):
        fail("independent sequence floor is outside the verified continuation")
    # Exact historical receipts and acknowledgments MUST be a prefix.
    # A different but validly signed history is a fork, not continuity.
    if any(trust.encode_json(a) != trust.encode_json(b)
           for a, b in zip(old, new)):
        fail("signed historical prefix has forked or been rewritten")

    package, package_sha = strict_pinned(
        args.trusted_latest_package, args.trusted_package_sha256,
        "latest independently retained signed package",
        custodian.MAX_PACKAGE_BYTES)
    expected_latest = {"schema": custodian.PACKAGE_SCHEMA, **new[-1]}
    if package != expected_latest:
        fail("candidate latest acknowledgment differs from independently retained checkpoint")
    checker = argparse.Namespace(
        expected_receiver_id=args.receiver_id,
        trusted_source_key_id=args.source_key_id,
        trusted_source_public_key=args.source_public_key,
        trusted_ack_key_id=args.ack_key_id,
        trusted_ack_public_key=args.ack_public_key,
        minimum_sequence=args.minimum_sequence,
        state_dir=None,
    )
    with contextlib.redirect_stdout(io.StringIO()):
        custodian.independent_verify_package(package, checker)
    if package["ack"]["sequence"] != len(new):
        fail("latest independently signed sequence disagrees with ledger length")
    return {
        "schema": SCHEMA,
        "status": "verified-signed-prefix",
        "baseline_sha256": original_sha,
        "candidate_sha256": successor_sha,
        "independent_latest_package_sha256": package_sha,
        "receiver_id": args.receiver_id,
        "source_key_id": args.source_key_id,
        "ack_key_id": args.ack_key_id,
        "baseline_sequence": len(old),
        "candidate_sequence": len(new),
        "new_acknowledgments": len(new) - len(old),
        "latest_ack_sha256": custodian.digest(package["ack"]),
        "independent_host_or_custody_proven": False,
        "authorizes_import_deployment_or_key_rotation": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline-ledger", type=Path, required=True)
    p.add_argument("--baseline-sha256", required=True)
    p.add_argument("--candidate-ledger", type=Path, required=True)
    p.add_argument("--candidate-sha256", required=True)
    p.add_argument("--trusted-latest-package", type=Path, required=True)
    p.add_argument("--trusted-package-sha256", required=True)
    p.add_argument("--receiver-id", required=True)
    p.add_argument("--source-key-id", required=True)
    p.add_argument("--source-public-key", type=Path, required=True)
    p.add_argument("--ack-key-id", required=True)
    p.add_argument("--ack-public-key", type=Path, required=True)
    p.add_argument("--minimum-sequence", type=int, required=True)
    args = p.parse_args()
    try:
        print(json.dumps(prove(args), sort_keys=True, separators=(",", ":")))
        return 0
    except (PrefixError, custodian.CustodianError,
            custodian.witness.WitnessError, trust.TrustError,
            OSError, ValueError, TypeError) as exc:
        print("NEXUS WITNESS LEDGER CONTINUITY DENIED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
