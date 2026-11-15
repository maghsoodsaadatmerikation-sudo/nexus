#!/usr/bin/env python3
"""Operator-controlled offline trust keys and single-file replay ledger.

This tool NEVER authorizes NEXUS HTTP import or attests remote adapter execution.
Requires a private POSIX operator directory and real OpenSSL Ed25519 verification.
"""

import argparse
import base64
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

STATE_SCHEMA = "nexus.workspace.offline-trust-state.v1"
STATE_FILE = "trust-state.json"
MAX_STATE_BYTES = 2 * 1024 * 1024
MAX_KEY_BYTES = 8192
MAX_KEYS = 64
MAX_WORKSPACES = 2048
KEY_ROLE = "offline_witness"  # No runtime_import or execution authority.
ED25519_DER_PREFIX = bytes.fromhex("302a300506032b6570032100")
SHA256_HEX = re.compile(r"[0-9a-f]{64}\Z")
KEY_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")

SCRIPT_DIR = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "nexus_detached_attestation", SCRIPT_DIR / "workspace-attestation.py"
)
if spec is None or spec.loader is None:
    raise RuntimeError("detached Ed25519 verifier not available")
attestation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(attestation)


class TrustError(Exception):
    pass


def fail(reason):
    raise TrustError(reason)


def encode_json(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def open_no_symlinks(path, max_bytes):
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise TrustError("missing or unsafe input file") from exc
    with os.fdopen(fd, "rb") as stream:
        meta = os.fstat(stream.fileno())
        if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1:
            fail("input must be a regular unlinked file")
        if meta.st_size > max_bytes:
            fail("input exceeds size cap")
        data = stream.read(max_bytes + 1)
    if not data or len(data) > max_bytes:
        fail("empty or oversized input")
    return data


def strict_json(raw):
    try:
        return attestation.decode_json(raw)
    except attestation.AttestationError as exc:
        raise TrustError("invalid or ambiguous JSON") from exc


def valid_key_id(value):
    if not isinstance(value, str) or not KEY_ID.fullmatch(value):
        fail("invalid key ID")
    return value


def fingerprint(der):
    return hashlib.sha256(der).hexdigest()


def validate_public_der(der):
    if not isinstance(der, bytes) or len(der) != 44 or not der.startswith(ED25519_DER_PREFIX):
        fail("public key is not a canonical Ed25519 SubjectPublicKeyInfo")
    return der


def derive_ed25519_public_der(path):
    raw = open_no_symlinks(path, MAX_KEY_BYTES)
    with tempfile.TemporaryDirectory(prefix="nexus-public-key-") as directory:
        source = Path(directory) / "supplied.pem"
        source.write_bytes(raw)
        try:
            r = subprocess.run(
                ["openssl", "pkey", "-pubin", "-in", str(source),
                 "-outform", "DER"],
                capture_output=True, timeout=15, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise TrustError("cannot check operator-supplied public key") from exc
    if r.returncode != 0:
        fail("invalid public key")
    return validate_public_der(r.stdout)


def public_key_pem(der):
    validate_public_der(der)
    encoded = base64.b64encode(der).decode("ascii")
    return ("-----BEGIN PUBLIC KEY-----\n" +
            "\n".join(encoded[i:i + 64] for i in range(0, len(encoded), 64)) +
            "\n-----END PUBLIC KEY-----\n").encode("ascii")


def empty_state():
    return {"schema": STATE_SCHEMA, "keys": {}, "workspaces": {}}


def validate_state(value):
    if (not isinstance(value, dict) or set(value) != {"schema", "keys", "workspaces"}
            or value["schema"] != STATE_SCHEMA
            or not isinstance(value["keys"], dict)
            or not isinstance(value["workspaces"], dict)
            or len(value["keys"]) > MAX_KEYS
            or len(value["workspaces"]) > MAX_WORKSPACES):
        fail("invalid, corrupted or unsupported trust state")
    seen_fingerprints = set()
    for key_id, item in value["keys"].items():
        valid_key_id(key_id)
        if (not isinstance(item, dict)
                or set(item) != {"public_key_der_base64", "fingerprint_sha256", "role", "status"}
                or item["role"] != KEY_ROLE or item["status"] not in ("active", "revoked")
                or not isinstance(item["public_key_der_base64"], str)
                or not isinstance(item["fingerprint_sha256"], str)
                or not SHA256_HEX.fullmatch(item["fingerprint_sha256"])):
            fail("untrusted key state")
        try:
            der = base64.b64decode(item["public_key_der_base64"], validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise TrustError("invalid stored public key") from exc
        validate_public_der(der)
        if fingerprint(der) != item["fingerprint_sha256"]:
            fail("stored public key fingerprint mismatch")
        if item["fingerprint_sha256"] in seen_fingerprints:
            fail("public key reused across independent key IDs")
        seen_fingerprints.add(item["fingerprint_sha256"])
    for workspace_id, item in value["workspaces"].items():
        try:
            attestation.checked_token(workspace_id, "ledger workspace ID")
        except attestation.AttestationError as exc:
            raise TrustError("invalid ledger workspace ID") from exc
        if (not isinstance(item, dict)
                or set(item) != {"event_count", "events_sha256", "snapshot_sha256", "key_id"}
                or type(item["event_count"]) is not int
                or not 1 <= item["event_count"] <= 100_000
                or not isinstance(item["events_sha256"], str)
                or not SHA256_HEX.fullmatch(item["events_sha256"])
                or not isinstance(item["snapshot_sha256"], str)
                or not SHA256_HEX.fullmatch(item["snapshot_sha256"])
                or item["key_id"] not in value["keys"]):
            fail("invalid monotonic witness ledger")
    return value


def write_state(directory_fd, value):
    raw = encode_json(validate_state(value))
    if len(raw) > MAX_STATE_BYTES:
        fail("trust state capacity exceeded")
    temporary = ".trust-next-" + os.urandom(12).hex()
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(temporary, flags, 0o600, dir_fd=directory_fd)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, STATE_FILE, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        os.fsync(directory_fd)
    finally:
        try:
            os.unlink(temporary, dir_fd=directory_fd)
        except FileNotFoundError:
            pass


def read_state(directory_fd):
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(STATE_FILE, flags, dir_fd=directory_fd)
    except OSError as exc:
        raise TrustError("trust registry missing; explicit init required") from exc
    with os.fdopen(fd, "rb") as stream:
        meta = os.fstat(stream.fileno())
        if (not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1
                or meta.st_uid != os.geteuid()
                or meta.st_mode & 0o077 or meta.st_size > MAX_STATE_BYTES):
            fail("untrusted registry file ownership, links or permissions")
        data = stream.read(MAX_STATE_BYTES + 1)
    if not data or len(data) > MAX_STATE_BYTES:
        fail("missing or oversized registry")
    return validate_state(strict_json(data))


def protected_directory(path):
    if os.name != "posix":
        fail("operator trust state requires POSIX filesystem locking")
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise TrustError("trust directory missing or unsafe") from exc
    try:
        meta = os.fstat(fd)
        if (not stat.S_ISDIR(meta.st_mode) or meta.st_uid != os.geteuid()
                or meta.st_mode & 0o077):
            fail("trust directory must be operator-owned and private (0700)")
        # Cooperative operations serialize on the DIRECTORY descriptor, not an
        # attacker-replaceable lock file; lock is released on process exit.
        fcntl.flock(fd, fcntl.LOCK_EX)
        current = os.stat(path, follow_symlinks=False)
        if (current.st_dev, current.st_ino) != (meta.st_dev, meta.st_ino):
            fail("trust directory replaced while opening")
        return fd
    except Exception:
        os.close(fd)
        raise


def initialize(path):
    if os.name != "posix":
        fail("operator trust state requires POSIX")
    try:
        os.mkdir(path, 0o700)
    except OSError as exc:
        raise TrustError("trust directory already exists or cannot be created") from exc
    fd = protected_directory(path)
    try:
        write_state(fd, empty_state())
    finally:
        os.close(fd)
    print("OFFLINE TRUST STORE CREATED: no key trusted and no import permission")


def key_record(der):
    return {
        "public_key_der_base64": base64.b64encode(der).decode("ascii"),
        "fingerprint_sha256": fingerprint(der),
        "role": KEY_ROLE, "status": "active",
    }


def enroll(state, key_id, der):
    valid_key_id(key_id)
    if key_id in state["keys"] or len(state["keys"]) >= MAX_KEYS:
        fail("key ID reused or trust key capacity exceeded")
    if any(item["fingerprint_sha256"] == fingerprint(der)
           for item in state["keys"].values()):
        fail("public key already enrolled under another ID")
    state["keys"][key_id] = key_record(der)


def event_digest(events):
    return hashlib.sha256(json.dumps(
        events, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def checked_events(raw):
    doc = strict_json(raw)
    if not isinstance(doc, dict) or not isinstance(doc.get("events"), list):
        fail("snapshot has no valid event history")
    events = doc["events"]
    if not 1 <= len(events) <= 100_000:
        fail("invalid event count")
    for index, event in enumerate(events):
        if (not isinstance(event, dict)
                or type(event.get("sequence")) is not int
                or event["sequence"] != index):
            fail("invalid, missing or out-of-order event sequence")
    if events[0].get("kind") != "WorkspaceCreated":
        fail("snapshot does not begin with workspace creation")
    return events


def verify_witness(state, args):
    raw = open_no_symlinks(args.snapshot, attestation.MAX_SNAPSHOT_BYTES)
    sidecar = open_no_symlinks(args.attestation, attestation.MAX_ATTESTATION_BYTES)
    witness = strict_json(sidecar)
    if not isinstance(witness, dict) or set(witness) != attestation.REQUIRED_FIELDS:
        fail("invalid detached attestation")
    key_id = valid_key_id(witness.get("key_id"))
    key = state["keys"].get(key_id)
    if not key or key["status"] != "active" or key["role"] != KEY_ROLE:
        fail("witness signing key not active and independently trusted")
    try:
        actual_id = attestation.snapshot_info(raw)
    except attestation.AttestationError as exc:
        raise TrustError("malformed or non-machine witness snapshot") from exc
    if actual_id != args.workspace_id:
        fail("witness destination mismatch")
    der = base64.b64decode(key["public_key_der_base64"], validate=True)
    validate_public_der(der)
    if fingerprint(der) != key["fingerprint_sha256"]:
        fail("stored trusted key fingerprint mismatch")

    # Freeze bytes under a private directory before OpenSSL uses file paths.
    # The trusted DER comes from the operator registry, never the sidecar.
    with tempfile.TemporaryDirectory(prefix="nexus-trusted-witness-") as directory:
        root = Path(directory)
        snapshot_file = root / "snapshot.json"
        sidecar_file = root / "attestation.json"
        public_file = root / "trusted.pem"
        snapshot_file.write_bytes(raw)
        sidecar_file.write_bytes(sidecar)
        public_file.write_bytes(public_key_pem(der))
        try:
            verified = subprocess.run([
                sys.executable, str(SCRIPT_DIR / "workspace-attestation.py"),
                "verify", "--snapshot", str(snapshot_file),
                "--attestation", str(sidecar_file),
                "--expected-workspace-id", actual_id,
                "--trusted-key-id", key_id,
                "--trusted-public-key", str(public_file),
            ], capture_output=True, timeout=35, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise TrustError("detached signature verifier unavailable") from exc
    if verified.returncode != 0:
        fail("detached Ed25519 verification failed")
    return raw, key_id


def record_witness(state, raw, key_id, workspace_id):
    events = checked_events(raw)
    previous = state["workspaces"].get(workspace_id)
    if previous is not None:
        if len(events) <= previous["event_count"]:
            fail("replayed or rolled-back witness revision")
        if event_digest(events[:previous["event_count"]]) != previous["events_sha256"]:
            fail("witness event history fork or rewrite")
    elif len(state["workspaces"]) >= MAX_WORKSPACES:
        fail("workspace ledger capacity exceeded")
    state["workspaces"][workspace_id] = {
        "event_count": len(events),
        "events_sha256": event_digest(events),
        "snapshot_sha256": hashlib.sha256(raw).hexdigest(),
        "key_id": key_id,
    }


def run(args):
    if args.action == "init":
        initialize(args.state_dir)
        return
    fd = protected_directory(args.state_dir)
    try:
        state = read_state(fd)  # Missing/corrupt registry must fail closed.
        if args.action == "enroll":
            enroll(state, args.key_id, derive_ed25519_public_der(args.public_key))
            write_state(fd, state)
            print("PUBLIC KEY ENROLLED: offline_witness role ONLY; no import authority")
        elif args.action == "revoke":
            key_id = valid_key_id(args.key_id)
            item = state["keys"].get(key_id)
            if not item or item["status"] != "active":
                fail("key absent or already revoked")
            item["status"] = "revoked"
            write_state(fd, state)
            print("PUBLIC KEY REVOKED: old signature verification now denied")
        elif args.action == "rotate":
            old_id = valid_key_id(args.old_key_id)
            if old_id not in state["keys"] or state["keys"][old_id]["status"] != "active":
                fail("rotation source must be active")
            enroll(state, args.new_key_id, derive_ed25519_public_der(args.new_public_key))
            state["keys"][old_id]["status"] = "revoked"
            write_state(fd, state)
            print("KEY ROTATED ATOMICALLY: old key revoked; new offline witness key active")
        elif args.action in ("inspect", "record"):
            raw, key_id = verify_witness(state, args)
            if args.action == "record":
                record_witness(state, raw, key_id, args.workspace_id)
                write_state(fd, state)
                print("OFFLINE WITNESS RECORDED: append-only history checked; NOT imported")
            else:
                print("TRUSTED OFFLINE SIGNATURE VERIFIED: replay ledger unchanged; NOT imported")
        elif args.action == "status":
            report = {
                "schema": STATE_SCHEMA,
                "keys": {key_id: {
                    "fingerprint_sha256": item["fingerprint_sha256"],
                    "role": item["role"], "status": item["status"],
                } for key_id, item in sorted(state["keys"].items())},
                "workspace_count": len(state["workspaces"]),
            }
            print(json.dumps(report, sort_keys=True))
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for command in ("init", "enroll", "revoke", "rotate", "inspect", "record", "status"):
        action = sub.add_parser(command)
        action.add_argument("--state-dir", type=Path, required=True)
        if command in ("enroll", "revoke"):
            action.add_argument("--key-id", required=True)
        if command == "enroll":
            action.add_argument("--public-key", type=Path, required=True)
        if command == "rotate":
            action.add_argument("--old-key-id", required=True)
            action.add_argument("--new-key-id", required=True)
            action.add_argument("--new-public-key", type=Path, required=True)
        if command in ("inspect", "record"):
            action.add_argument("--snapshot", type=Path, required=True)
            action.add_argument("--attestation", type=Path, required=True)
            action.add_argument("--workspace-id", required=True)
    args = parser.parse_args()
    try:
        run(args)
    except (TrustError, OSError, ValueError, TypeError) as exc:
        print("OFFLINE TRUST DENIED: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
