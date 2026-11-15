#!/usr/bin/env python3
"""Offline append-only event ledger for one-time two-observer witness challenges.

The separate operator retains an independent exact registry SHA-256 checkpoint
before each update. Never a host-independence proof or deployment authority.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import stat
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "nexus_challenge_two_custody", HERE / "workspace-witness-two-custody-evidence.py")
if spec is None or spec.loader is None:
    raise RuntimeError("two-custody evidence verifier unavailable")
two = importlib.util.module_from_spec(spec)
stager = two.stager
trust = two.trust
v2 = two.v2

SCHEMA = "nexus.offsite.observer-challenge-ledger.v1"
FILE = "challenges.json"
ISSUE_KEYS = {"kind", "sequence", "previous_event_sha256", "challenge_hex"}
CONSUME_KEYS = ISSUE_KEYS | {
    "origin_report_sha256", "recovery_report_sha256",
    "bridge_sha256", "latest_sequence", "latest_ack_sha256",
}
MAX_EVENTS = 256
MAX_BYTES = 128 * 1024
GENESIS = "0" * 64


class LedgerError(Exception):
    pass


def fail(message):
    raise LedgerError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def pin(value, label):
    if not isinstance(value, str) or not v2.HEX.fullmatch(value):
        fail("independent " + label + " SHA-256 pin is required")
    return value


def validate(data):
    if (not isinstance(data, dict) or set(data) != {"schema", "events"}
            or data["schema"] != SCHEMA or not isinstance(data["events"], list)
            or len(data["events"]) > MAX_EVENTS):
        fail("invalid bounded challenge ledger schema")
    opened, consumed = set(), set()
    previous = GENESIS
    for sequence, event in enumerate(data["events"], 1):
        if not isinstance(event, dict) or event.get("kind") not in ("issue", "consume"):
            fail("unrecognized event in challenge history")
        kind = event["kind"]
        if set(event) != (ISSUE_KEYS if kind == "issue" else CONSUME_KEYS):
            fail("challenge event has invalid fields")
        ch = two.challenge(event["challenge_hex"])
        if (type(event["sequence"]) is not int or event["sequence"] != sequence
                or event["previous_event_sha256"] != previous):
            fail("challenge event chain fork, duplicate or sequence rollback")
        if kind == "issue":
            if ch in opened:
                fail("challenge was already issued in this ledger")
            opened.add(ch)
        else:
            if ch not in opened or ch in consumed:
                fail("challenge consumed without unique earlier issuance")
            for key in ("origin_report_sha256", "recovery_report_sha256",
                        "bridge_sha256", "latest_ack_sha256"):
                pin(event[key], key)
            if (type(event["latest_sequence"]) is not int
                    or event["latest_sequence"] < 2):
                fail("invalid verified signed history sequence")
            if event["origin_report_sha256"] == event["recovery_report_sha256"]:
                fail("both custody roles cannot use identical signed report")
            consumed.add(ch)
        previous = digest(trust.encode_json(event))
    encoded = trust.encode_json(data)
    if len(encoded) > MAX_BYTES:
        fail("challenge ledger exceeds size limit")
    return opened, consumed, previous


def read_locked(fd):
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        handle = os.open(FILE, flags, dir_fd=fd)
    except OSError as exc:
        raise LedgerError("challenge ledger absent or unsafe; explicit init required") from exc
    with os.fdopen(handle, "rb") as f:
        meta = os.fstat(f.fileno())
        if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid()
                or meta.st_nlink != 1 or meta.st_mode & 0o077
                or not 0 < meta.st_size <= MAX_BYTES):
            fail("challenge ledger must be an operator-owned private regular file")
        raw = f.read(MAX_BYTES + 1)
    if not raw or len(raw) > MAX_BYTES:
        fail("challenge ledger missing or oversized")
    data = trust.strict_json(raw)
    if trust.encode_json(data) != raw:
        fail("challenge ledger is noncanonical or damaged")
    validate(data)
    return data, raw


def write_locked(fd, data, expected_hash):
    validate(data)
    raw = trust.encode_json(data)
    if expected_hash is None:
        try:
            os.stat(FILE, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            fail("existing challenge history cannot be overwritten by init")
    elif digest(read_locked(fd)[1]) != expected_hash:
        fail("registry changed since previous pinned hash; conflicting update")
    name = ".challenges-next-" + secrets.token_hex(12)
    flags = (os.O_WRONLY | os.O_CREAT | os.O_EXCL
             | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0))
    handle = os.open(name, flags, 0o600, dir_fd=fd)
    try:
        with os.fdopen(handle, "wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, FILE, src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
    finally:
        try:
            os.unlink(name, dir_fd=fd)
        except FileNotFoundError:
            pass
    if read_locked(fd)[1] != raw:
        fail("durable challenge ledger read-back differs after fsync")
    return digest(raw)


def init(args):
    if not args.registry.is_absolute():
        fail("challenge registry requires an explicit absolute directory")
    try:
        os.mkdir(args.registry, 0o700)
    except OSError as exc:
        raise LedgerError("registry path must be a new, private directory") from exc
    # Same single-filesystem crash guarantees as the v2 offline restore.
    recovery_spec = importlib.util.spec_from_file_location(
        "nexus_challenge_recovery_sync", HERE / "workspace-witness-v2-recovery.py")
    recovery = importlib.util.module_from_spec(recovery_spec)
    recovery_spec.loader.exec_module(recovery)
    # Parent can be an operator-controlled private staging volume; tests may
    # intentionally use private tempfile roots.
    recovery.sync_new_directory_parent(args.registry)
    fd = trust.protected_directory(args.registry)
    try:
        stager.assert_directory_identity(args.registry, fd)
        sha = write_locked(fd, {"schema": SCHEMA, "events": []}, None)
        stager.assert_directory_identity(args.registry, fd)
    finally:
        os.close(fd)
    return {"schema": "nexus.offsite.observer-challenge-ledger-result.v1",
            "status": "initialized-private-challenge-ledger",
            "registry_sha256": sha, "events": 0,
            "production_release_authorized": False}


def open_registry(args):
    if not args.registry.is_absolute():
        fail("challenge registry requires an explicit absolute directory")
    fd = trust.protected_directory(args.registry)
    try:
        stager.assert_directory_identity(args.registry, fd)
        data, raw = read_locked(fd)
        if digest(raw) != pin(args.expected_registry_sha256, "registry"):
            fail("observed registry differs from independently pinned predecessor")
        return fd, data, raw
    except Exception:
        os.close(fd)
        raise


def event(data, kind, challenge_hex, extra=None):
    prior = (digest(trust.encode_json(data["events"][-1]))
             if data["events"] else GENESIS)
    return {
        "kind": kind,
        "sequence": len(data["events"]) + 1,
        "previous_event_sha256": prior,
        "challenge_hex": challenge_hex,
        **(extra or {}),
    }


def issue(args):
    fd, data, before = open_registry(args)
    try:
        if len(data["events"]) >= MAX_EVENTS:
            fail("challenge registry capacity reached; unsafe recycling denied")
        used, _, _ = validate(data)
        new_challenge = ""
        for _ in range(8):
            candidate = secrets.token_hex(32)
            if candidate != GENESIS and candidate not in used:
                new_challenge = candidate
                break
        if not new_challenge:
            fail("unique cryptographic challenge generation failed")
        data["events"].append(event(data, "issue", new_challenge))
        stager.assert_directory_identity(args.registry, fd)
        next_sha = write_locked(fd, data, digest(before))
        stager.assert_directory_identity(args.registry, fd)
    finally:
        os.close(fd)
    return {"schema": "nexus.offsite.observer-challenge-ledger-result.v1",
            "status": "new-challenge-issued",
            "challenge_hex": new_challenge,
            "registry_sha256": next_sha,
            "event_count": len(data["events"]),
            "independent_custody_proven": False,
            "production_release_authorized": False}


def consume(args):
    fd, data, before = open_registry(args)
    try:
        used, consumed, _ = validate(data)
        challenge = two.challenge(args.challenge_hex)
        if challenge not in used:
            fail("challenge has never been issued by independently pinned registry")
        if challenge in consumed:
            fail("challenge already consumed; duplicate signed observer reports denied")
        if len(data["events"]) >= MAX_EVENTS:
            fail("challenge registry capacity reached")
        # Full prior history, exact signed candidate, and both detached role
        # signatures are cryptographically verified BEFORE the ledger commits.
        pair = two.verify_pair(args)
        if (pair["status"] != "two-distinct-signer-observations-verified"
                or pair["challenge_hex"] != challenge):
            fail("two observer reports do not authorize the issued challenge")
        data["events"].append(event(data, "consume", challenge, {
            "origin_report_sha256": args.origin_report_sha256,
            "recovery_report_sha256": args.recovery_report_sha256,
            "bridge_sha256": pair["bridge_sha256"],
            "latest_sequence": pair["latest_sequence"],
            "latest_ack_sha256": pair["latest_ack_sha256"],
        }))
        stager.assert_directory_identity(args.registry, fd)
        next_sha = write_locked(fd, data, digest(before))
        stager.assert_directory_identity(args.registry, fd)
    finally:
        os.close(fd)
    return {"schema": "nexus.offsite.observer-challenge-ledger-result.v1",
            "status": "one-time-observer-evidence-consumed",
            "registry_sha256": next_sha,
            "event_count": len(data["events"]),
            "latest_sequence": pair["latest_sequence"],
            "challenge_hex": challenge,
            "physical_host_independence_proven": False,
            "production_release_authorized": False}


def inspect(args):
    fd, data, raw = open_registry(args)
    try:
        used, consumed, last = validate(data)
        stager.assert_directory_identity(args.registry, fd)
        return {"schema": "nexus.offsite.observer-challenge-ledger-result.v1",
                "status": "verified-pinned-challenge-registry",
                "registry_sha256": digest(raw),
                "event_count": len(data["events"]),
                "last_event_sha256": last,
                "pending_challenges": sorted(used - consumed),
                "consumed_count": len(consumed),
                "physical_host_independence_proven": False,
                "production_release_authorized": False}
    finally:
        os.close(fd)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    modes = p.add_subparsers(dest="mode", required=True)
    initialize = modes.add_parser("init")
    initialize.add_argument("--registry", type=Path, required=True)
    for label in ("issue", "inspect", "consume"):
        mode = modes.add_parser(label)
        mode.add_argument("--registry", type=Path, required=True)
        mode.add_argument("--expected-registry-sha256", required=True)
        if label == "consume":
            two.common(mode)
            mode.add_argument("--approved-bridge", type=Path, required=True)
            for flag in ("origin-report", "recovery-report",
                         "origin-public-key", "recovery-public-key"):
                mode.add_argument("--" + flag, type=Path, required=True)
            for flag in ("origin-report-sha256", "recovery-report-sha256",
                         "origin-observer-id", "recovery-observer-id"):
                mode.add_argument("--" + flag, required=True)
    args = p.parse_args()
    try:
        result = {"init": init, "issue": issue, "inspect": inspect,
                  "consume": consume}[args.mode](args)
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
        return 0
    except (LedgerError, two.ObservationError, stager.StageError,
            v2.EpochError, v2.transition.ConsentError,
            v2.custodian.CustodianError,
            v2.custodian.witness.WitnessError,
            trust.TrustError, OSError, TypeError, ValueError, KeyError) as exc:
        print("NEXUS ONE-TIME CHALLENGE LEDGER DENIED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
