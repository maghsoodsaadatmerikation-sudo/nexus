#!/usr/bin/env python3
"""Send and retrieve NEXUS witness receipts over explicitly pinned OpenSSH.

No remote service is provisioned by this code. The independent recipient must
configure authorized_keys forced-command restrictions and separate key custody.
Only a signed custodian package is returned as success; transport exit status
is insufficient. Never send a Workspace, bearer token or private signing key.
"""

import argparse
import importlib.util
import io
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from contextlib import redirect_stdout

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "nexus_transport_custodian", HERE / "workspace-witness-custodian.py"
)
if spec is None or spec.loader is None:
    raise RuntimeError("custodian verification unavailable")
custodian = importlib.util.module_from_spec(spec)
spec.loader.exec_module(custodian)
trust = custodian.trust

HOST = re.compile(r"[A-Za-z0-9][A-Za-z0-9.-]{0,252}\Z")
ACCOUNT = re.compile(r"[a-z_][a-z0-9_-]{0,31}\Z")
MAX_PACKAGE = 2 * custodian.witness.MAX_RECEIPT_BYTES
SSH_TIMEOUT_SECONDS = 40


class TransportError(Exception):
    pass


def reject(reason):
    raise TransportError(reason)


def checked_file(path, *, private=False):
    if not path.is_absolute():
        reject("explicit absolute trusted file path required")
    try:
        meta = path.lstat()
    except OSError as exc:
        raise TransportError("trusted SSH credential or host-key file missing") from exc
    if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid()
            or meta.st_nlink != 1 or meta.st_mode & 0o022
            or (private and meta.st_mode & 0o077)
            or meta.st_size == 0 or meta.st_size > 8192):
        reject("untrusted SSH credential or pinned host key file")
    return path


def ssh_args(args, action):
    if not HOST.fullmatch(args.host) or not ACCOUNT.fullmatch(args.user):
        reject("invalid destination host or SSH account")
    if not 1 <= args.port <= 65535:
        reject("invalid SSH destination port")
    known_hosts = checked_file(args.known_hosts)
    identity = checked_file(args.identity, private=True)
    binary = shutil.which("ssh")
    if not binary:
        reject("OpenSSH client not installed")
    return [
        binary, "-F", "/dev/null", "-T",
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=yes",
        "-o", f"UserKnownHostsFile={known_hosts}",
        "-o", "GlobalKnownHostsFile=/dev/null",
        "-o", "IdentitiesOnly=yes",
        "-o", "IdentityAgent=none",
        "-o", "ForwardAgent=no",
        "-o", "ClearAllForwardings=yes",
        "-o", "ControlMaster=no",
        "-o", "ProxyCommand=none",
        "-o", "ProxyJump=none",
        "-o", "PermitLocalCommand=no",
        "-o", "UpdateHostKeys=no",
        "-o", "ConnectTimeout=10",
        "-o", "ConnectionAttempts=1",
        "-i", str(identity), "-p", str(args.port),
        "-l", args.user, args.host, "nexus-witness-v1 " + action,
    ]


def exchange(args, action, raw=b""):
    command = ssh_args(args, action)
    try:
        p = subprocess.run(
            command, input=raw, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=SSH_TIMEOUT_SECONDS, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TransportError(
            "SSH transport unavailable or timed out; receipt status UNKNOWN; retry exact receipt"
        ) from exc
    if p.returncode != 0:
        reject("SSH receiver denied or transport failed; receipt status UNKNOWN; retry exact receipt")
    if not p.stdout or len(p.stdout) > MAX_PACKAGE:
        reject("oversized, empty or missing authenticated receiver response")
    try:
        return trust.strict_json(p.stdout)
    except trust.TrustError as exc:
        raise TransportError("receiver returned invalid or ambiguous JSON") from exc


def verify_package(package, args):
    # Validate both signatures and receiver ID using independently pinned
    # source and custodian public keys, not keys supplied by remote JSON.
    auth = argparse.Namespace(
        expected_receiver_id=args.receiver_id,
        trusted_source_key_id=args.source_key_id,
        trusted_source_public_key=args.source_public_key,
        trusted_ack_key_id=args.ack_key_id,
        trusted_ack_public_key=args.ack_public_key,
        minimum_sequence=args.minimum_sequence,
        state_dir=args.state_dir,
    )
    try:
        with redirect_stdout(io.StringIO()):
            custodian.independent_verify_package(package, auth)
    except (custodian.CustodianError, custodian.witness.WitnessError,
            trust.TrustError, OSError, ValueError, TypeError) as exc:
        raise TransportError("receiver's signed acknowledgment is not independently valid") from exc


def write_package(path, package):
    if not path.is_absolute():
        reject("signed acknowledgment destination must be an explicit absolute path")
    raw = trust.encode_json(package)
    if len(raw) > MAX_PACKAGE:
        reject("signed acknowledgment exceeds output size limit")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as exc:
        raise TransportError("signed acknowledgment destination exists or is unwritable") from exc
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise
    parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


def run(args):
    if args.minimum_sequence < 1:
        reject("minimum acknowledged sequence must be explicitly pinned and positive")
    # Check source and recipient public keys even if the transport fails.
    custodian.secure_inputs(
        args.source_public_key, args.ack_public_key,
        args.source_key_id, args.ack_key_id,
    )
    trust.valid_key_id(args.receiver_id)
    source_receipt = None
    raw = b""
    if args.action == "send":
        raw = trust.open_no_symlinks(args.receipt, custodian.witness.MAX_RECEIPT_BYTES)
        source_receipt = trust.strict_json(raw)
        remote_action = "receive"
    else:
        remote_action = "latest"
    package = exchange(args, remote_action, raw)
    verify_package(package, args)
    if source_receipt is not None and package["receipt"] != source_receipt:
        reject("receiver acknowledgment does not match the exact submitted receipt")
    write_package(args.output, package)
    print(
        "PINNED SSH RECEIPT VERIFIED AND SAVED: seq="
        + str(package["ack"]["sequence"])
        + "; external custody is operator-managed, NOT deployed by NEXUS"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="action", required=True)
    for action in ("send", "latest"):
        command = modes.add_parser(action)
        command.add_argument("--host", required=True)
        command.add_argument("--user", required=True)
        command.add_argument("--port", type=int, default=22)
        command.add_argument("--known-hosts", type=Path, required=True)
        command.add_argument("--identity", type=Path, required=True)
        command.add_argument("--receiver-id", required=True)
        command.add_argument("--source-key-id", required=True)
        command.add_argument("--source-public-key", type=Path, required=True)
        command.add_argument("--ack-key-id", required=True)
        command.add_argument("--ack-public-key", type=Path, required=True)
        command.add_argument("--minimum-sequence", type=int, required=True)
        command.add_argument("--state-dir", type=Path)
        command.add_argument("--output", type=Path, required=True)
        if action == "send":
            command.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        run(args)
        return 0
    except (TransportError, custodian.CustodianError, trust.TrustError,
            OSError, ValueError, TypeError) as exc:
        print("PINNED SSH WITNESS DENIED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
