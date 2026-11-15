#!/usr/bin/env python3
"""Offline, three-party signed witness receiver KEY-TRANSITION CONSENT.

Proof of consent only. Does NOT replace recipient keys, change the receiver
ledger, authorize imports, or permit network commands. Each role signs in
separate custody; no execution step ever needs all three private keys.
"""

import argparse
import base64
import binascii
import contextlib
import hashlib
import importlib.util
import io
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "nexus_transition_custodian", HERE / "workspace-witness-custodian.py"
)
if spec is None or spec.loader is None:
    raise RuntimeError("NEXUS witness custodian verifier unavailable")
custodian = importlib.util.module_from_spec(spec)
spec.loader.exec_module(custodian)
trust = custodian.trust

SCHEMA = "nexus.offsite.receiver-key-transition-consent.v1"
PROPOSAL_SCHEMA = "nexus.offsite.receiver-key-transition-proposal.v1"
DOMAIN = b"NEXUS\x00receiver-key-transition-consent\x00Ed25519\x00v1\x00"
ROLES = ("source", "outgoing", "incoming")
PROPOSAL_KEYS = {
    "schema", "receiver_id", "source_key_id", "outgoing_ack_key_id",
    "incoming_ack_key_id", "source_public_sha256",
    "outgoing_public_sha256", "incoming_public_sha256",
    "exact_checkpoint_sha256", "latest_ack_sha256", "latest_sequence",
}
MAX_CONSENT_BYTES = 8192
SHA = re.compile(r"[a-f0-9]{64}\Z")


class ConsentError(Exception):
    pass


def fail(message):
    raise ConsentError(message)


def fingerprint(der):
    return hashlib.sha256(der).hexdigest()


def consent_preimage(role, proposal):
    if role not in ROLES:
        fail("unrecognized transition signer role")
    encoded = trust.encode_json(proposal)
    return DOMAIN + len(role).to_bytes(1, "big") + role.encode("ascii") + len(encoded).to_bytes(8, "big") + encoded


def parse_document(path):
    doc = trust.strict_json(trust.open_no_symlinks(path, MAX_CONSENT_BYTES))
    if (not isinstance(doc, dict) or set(doc) != {"schema", "proposal", "approvals"}
            or doc["schema"] != SCHEMA
            or not isinstance(doc["proposal"], dict)
            or set(doc["proposal"]) != PROPOSAL_KEYS
            or doc["proposal"]["schema"] != PROPOSAL_SCHEMA
            or not isinstance(doc["approvals"], dict)
            or any(role not in ROLES for role in doc["approvals"])):
        fail("invalid transition consent envelope")
    proposal = doc["proposal"]
    for k in ("receiver_id", "source_key_id", "outgoing_ack_key_id", "incoming_ack_key_id"):
        custodian.key_id(proposal[k])
    if len({
        proposal["source_key_id"], proposal["outgoing_ack_key_id"],
        proposal["incoming_ack_key_id"],
    }) != 3:
        fail("rotation signers must have distinct role key identifiers")
    for k in (
        "source_public_sha256", "outgoing_public_sha256",
        "incoming_public_sha256", "exact_checkpoint_sha256", "latest_ack_sha256",
    ):
        if not isinstance(proposal[k], str) or not SHA.fullmatch(proposal[k]):
            fail("invalid transition commitment digest")
    if type(proposal["latest_sequence"]) is not int or proposal["latest_sequence"] < 1:
        fail("invalid positive pinned acknowledgment sequence")
    if len({
        proposal["source_public_sha256"],
        proposal["outgoing_public_sha256"],
        proposal["incoming_public_sha256"],
    }) != 3:
        fail("transition signing keys must be cryptographically distinct")
    for role, signature in doc["approvals"].items():
        if not isinstance(signature, str):
            fail("signature encoding must be base64")
        try:
            raw = base64.b64decode(signature, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ConsentError("malformed detached signer approval") from exc
        if len(raw) != 64 or base64.b64encode(raw).decode("ascii") != signature:
            fail("invalid or noncanonical signer approval")
    return doc


def independent_latest(package_path, package_sha, expected, keys, floor):
    if not isinstance(package_sha, str) or not SHA.fullmatch(package_sha):
        fail("independently approved signed package SHA-256 is required")
    raw = trust.open_no_symlinks(package_path, 2 * custodian.witness.MAX_RECEIPT_BYTES)
    if fingerprint(raw) != package_sha:
        fail("previous signed package changed against independently pinned SHA-256")
    package = trust.strict_json(raw)
    args = argparse.Namespace(
        expected_receiver_id=expected,
        trusted_source_key_id=keys["source_id"],
        trusted_source_public_key=keys["source_public"],
        trusted_ack_key_id=keys["outgoing_id"],
        trusted_ack_public_key=keys["outgoing_public"],
        minimum_sequence=floor,
        state_dir=None,
    )
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            custodian.independent_verify_package(package, args)
    except (custodian.CustodianError, custodian.witness.WitnessError, trust.TrustError) as exc:
        raise ConsentError("latest receiver acknowledgment not independently valid") from exc
    return package


def public_keys(args):
    keys = {
        "source_id": args.source_key_id,
        "source_public": args.source_public_key,
        "outgoing_id": args.outgoing_ack_key_id,
        "outgoing_public": args.outgoing_ack_public_key,
        "incoming_id": args.incoming_ack_key_id,
        "incoming_public": args.incoming_ack_public_key,
    }
    for identifier in ("source_id", "outgoing_id", "incoming_id"):
        custodian.key_id(keys[identifier])
    if len({keys["source_id"], keys["outgoing_id"], keys["incoming_id"]}) != 3:
        fail("signer key IDs cannot be reused across roles")
    ders = {
        role: trust.derive_ed25519_public_der(keys[role + "_public"])
        for role in ROLES
    } if False else {
        "source": trust.derive_ed25519_public_der(keys["source_public"]),
        "outgoing": trust.derive_ed25519_public_der(keys["outgoing_public"]),
        "incoming": trust.derive_ed25519_public_der(keys["incoming_public"]),
    }
    if len(set(ders.values())) != 3:
        fail("source, outgoing and incoming signing keys must be different")
    return keys, ders


def prepare(args):
    custodian.key_id(args.receiver_id)
    keys, ders = public_keys(args)
    package = independent_latest(
        args.trusted_latest_package,
        args.trusted_package_sha256,
        args.receiver_id,
        keys,
        args.minimum_sequence,
    )
    # Require exact externally pinned sequence rather than just a minimum.
    if type(args.minimum_sequence) is not int or (
        args.minimum_sequence < 1
        or package["ack"]["sequence"] != args.minimum_sequence
    ):
        fail("transition checkpoint must be the exact, independently retained latest sequence")
    proposal = {
        "schema": PROPOSAL_SCHEMA,
        "receiver_id": args.receiver_id,
        "source_key_id": keys["source_id"],
        "outgoing_ack_key_id": keys["outgoing_id"],
        "incoming_ack_key_id": keys["incoming_id"],
        "source_public_sha256": fingerprint(ders["source"]),
        "outgoing_public_sha256": fingerprint(ders["outgoing"]),
        "incoming_public_sha256": fingerprint(ders["incoming"]),
        "exact_checkpoint_sha256": args.trusted_package_sha256,
        "latest_ack_sha256": custodian.digest(package["ack"]),
        "latest_sequence": args.minimum_sequence,
    }
    custodian.witness.write_exclusive(
        args.output, {"schema": SCHEMA, "proposal": proposal, "approvals": {}}
    )
    print("KEY TRANSITION PROPOSAL CREATED: 0/3 consent signatures; no key changed")


def sign(args):
    document = parse_document(args.input)
    if args.role in document["approvals"]:
        fail("a signer role cannot be approved twice")
    private_der = custodian.witness.private_signer(args.private_key)
    commitment = document["proposal"][args.role + "_public_sha256" if args.role == "source" else
                                       ("outgoing_public_sha256" if args.role == "outgoing" else "incoming_public_sha256")]
    if fingerprint(private_der) != commitment:
        fail("supplied private key is not the independently committed role identity")
    try:
        signature = trust.attestation.openssl(
            "sign", args.private_key, consent_preimage(args.role, document["proposal"])
        )
    except trust.attestation.AttestationError as exc:
        raise ConsentError("role-private-key signature was not produced") from exc
    if len(signature) != 64:
        fail("invalid Ed25519 consent signature")
    document["approvals"][args.role] = base64.b64encode(signature).decode("ascii")
    custodian.witness.write_exclusive(args.output, document)
    print("KEY TRANSITION APPROVAL CAPTURED: " + args.role +
          "; still NOT an active key rotation")


def verify(args):
    document = parse_document(args.input)
    if set(document["approvals"]) != set(ROLES):
        fail("source, outgoing and incoming parties must all consent")
    proposal = document["proposal"]
    if proposal["receiver_id"] != args.receiver_id:
        fail("receiver identity differs from independently approved operator")
    keys, ders = public_keys(args)
    for role, name in (
        ("source", "source_id"), ("outgoing", "outgoing_id"), ("incoming", "incoming_id")
    ):
        if proposal[("source_key_id" if role == "source"
                     else "outgoing_ack_key_id" if role == "outgoing"
                     else "incoming_ack_key_id")] != keys[name]:
            fail("signer identity changed across transition consent")
        if proposal[role + "_public_sha256"] != fingerprint(ders[role]):
            fail("signer public key changed across transition consent")
    package = independent_latest(
        args.trusted_latest_package, args.trusted_package_sha256,
        args.receiver_id, keys, args.minimum_sequence
    )
    if (type(args.minimum_sequence) is not int or
            proposal["latest_sequence"] != args.minimum_sequence or
            package["ack"]["sequence"] != args.minimum_sequence or
            proposal["exact_checkpoint_sha256"] != args.trusted_package_sha256 or
            proposal["latest_ack_sha256"] != custodian.digest(package["ack"])):
        fail("signed transition is stale or not tied to exact independent checkpoint")
    # Each role signs the same byte-exact typed proposal under a role-domain
    # prefix. Signed approval files may be passed between custody domains;
    # no single signer has to access another role's private key.
    for role in ROLES:
        with custodian.tempfile.TemporaryDirectory(prefix="nexus-key-consent-") as folder:
            pub = Path(folder) / "role.pub.pem"
            pub.write_bytes(custodian.public_from_der(ders[role]))
            try:
                trust.attestation.openssl(
                    "verify", pub, consent_preimage(role, proposal),
                    base64.b64decode(document["approvals"][role], validate=True)
                )
            except trust.attestation.AttestationError as exc:
                raise ConsentError("one of the independently approved role signatures is invalid") from exc
    print(
        "KEY TRANSITION CONSENT VERIFIED: 3/3 Ed25519 approvals, "
        "exact independent prior checkpoint, no actual key rotation or import authority"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    create = commands.add_parser("prepare")
    approved = commands.add_parser("verify")
    for tool in (create, approved):
        tool.add_argument("--receiver-id", required=True)
        tool.add_argument("--source-key-id", required=True)
        tool.add_argument("--source-public-key", type=Path, required=True)
        tool.add_argument("--outgoing-ack-key-id", required=True)
        tool.add_argument("--outgoing-ack-public-key", type=Path, required=True)
        tool.add_argument("--incoming-ack-key-id", required=True)
        tool.add_argument("--incoming-ack-public-key", type=Path, required=True)
        tool.add_argument("--trusted-latest-package", type=Path, required=True)
        tool.add_argument("--trusted-package-sha256", required=True)
        tool.add_argument("--minimum-sequence", type=int, required=True)
        if tool is create:
            tool.add_argument("--output", type=Path, required=True)
        else:
            tool.add_argument("--input", type=Path, required=True)
    signer = commands.add_parser("sign")
    signer.add_argument("--input", type=Path, required=True)
    signer.add_argument("--output", type=Path, required=True)
    signer.add_argument("--role", choices=ROLES, required=True)
    signer.add_argument("--private-key", type=Path, required=True)

    args = parser.parse_args()
    try:
        {"prepare": prepare, "sign": sign, "verify": verify}[args.action](args)
        return 0
    except (ConsentError, custodian.CustodianError,
            custodian.witness.WitnessError, trust.TrustError,
            OSError, ValueError, TypeError) as exc:
        print("NEXUS RECIPIENT KEY TRANSITION DENIED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
