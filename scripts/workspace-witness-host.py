#!/usr/bin/env python3
"""Root-pinned independent witness custodian SSH launcher (POSIX only).

An SSH account cannot select a ledger or a signing key from AcceptEnv,
SSH_ORIGINAL_COMMAND, arguments or client-supplied JSON. The administrator
fixes the exact --config path in the authorized_keys forced command.
This script neither installs an SSH host nor creates or backs up keys.
"""

import argparse
import os
from pathlib import Path
import stat
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import importlib.util

spec = importlib.util.spec_from_file_location(
    "nexus_host_custodian", HERE / "workspace-witness-custodian.py"
)
if spec is None or spec.loader is None:
    raise RuntimeError("receiver implementation unavailable")
custodian = importlib.util.module_from_spec(spec)
spec.loader.exec_module(custodian)
trust = custodian.trust

SCHEMA = "nexus.offsite.root-pinned-launch.v1"
CONFIG_KEYS = {"schema", "store_dir", "ack_private_key"}
CONFIG_MAX_BYTES = 4096
ALLOWED = {
    "nexus-witness-v1 receive": "receive-stdin",
    "nexus-witness-v1 latest": "latest",
}


class LaunchError(Exception):
    pass


def deny(message):
    raise LaunchError(message)


def check_root_path(path: Path):
    if not path.is_absolute() or path == Path("/"):
        deny("configuration must be an absolute root-owned file path")
    # Every path component must be a root-owned directory with no group/
    # other write access. lstat blocks symlink redirection at every level.
    current = Path("/")
    for component in path.parts[1:-1]:
        if component in (".", ".."):
            deny("unsafe configuration path component")
        current = current / component
        meta = current.lstat()
        if (not stat.S_ISDIR(meta.st_mode) or meta.st_uid != 0
                or meta.st_mode & 0o022):
            deny("configuration parent must be root-owned and non-writable")
    meta = path.lstat()
    if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != 0
            or meta.st_nlink != 1 or meta.st_mode & 0o022
            or meta.st_size < 1 or meta.st_size > CONFIG_MAX_BYTES):
        deny("configuration file must be root-owned regular, bounded and non-writable")
    return trust.strict_json(trust.open_no_symlinks(path, CONFIG_MAX_BYTES))


def private_key(path: Path, store: Path):
    if not path.is_absolute() or path == Path("/"):
        deny("signer private key requires absolute path")
    if path.resolve().is_relative_to(store.resolve()):
        deny("signing key must be outside the receiver ledger directory")
    meta = path.lstat()
    if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid()
            or meta.st_nlink != 1 or meta.st_mode & 0o077
            or meta.st_size == 0 or meta.st_size > trust.MAX_KEY_BYTES):
        deny("recipient signing key must be private, unlinked and owned by SSH account")


def checked_config(path: Path):
    doc = check_root_path(path)
    if (not isinstance(doc, dict) or set(doc) != CONFIG_KEYS
            or doc["schema"] != SCHEMA):
        deny("unsupported root-pinned receiver configuration")
    if (not isinstance(doc["store_dir"], str)
            or not isinstance(doc["ack_private_key"], str)):
        deny("invalid receiver configuration types")
    store = Path(doc["store_dir"])
    secret = Path(doc["ack_private_key"])
    if not store.is_absolute() or not secret.is_absolute():
        deny("receiver state paths must be absolute")
    fd = trust.protected_directory(store)
    try:
        data = custodian.read_store(fd)
    finally:
        os.close(fd)
    private_key(secret, store)
    # Preflight must prove signer custody is actually usable and corresponds
    # to the public key pinned by the existing, fully audited receiver ledger.
    # A missing or wrong key fails before SSH accepts any new receipt.
    try:
        private_der = custodian.witness.private_signer(secret)
    except custodian.witness.WitnessError as exc:
        raise LaunchError("recipient signer key unreadable or invalid") from exc
    _, pinned_ack_der = custodian.derived_keys(data)
    if private_der != pinned_ack_der:
        deny("signer private key does not match existing receiver trust identity")
    return store, secret


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "serve"))
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    try:
        if os.name != "posix":
            deny("POSIX root-owned configuration required")
        store, secret = checked_config(args.config)
        if args.action == "check":
            print("ROOT-PINNED CUSTODIAN: PRE-FLIGHT PASS (not deployed)")
            return 0
        requested = os.environ.get("SSH_ORIGINAL_COMMAND", "")
        if requested not in ALLOWED or not os.environ.get("SSH_CONNECTION"):
            deny("SSH forced-command not allowed")
        # No user-selected paths or shell. The custodian CLI is trusted code;
        # the environment is scrubbed before exec, not propagated from SSH.
        params = [
            sys.executable, "-I", str(HERE / "workspace-witness-custodian.py"),
            ALLOWED[requested], "--store", str(store),
        ]
        if requested == "nexus-witness-v1 receive":
            params.extend(["--ack-private-key", str(secret)])
        env = {"PATH": "/usr/bin:/bin", "LANG": "C", "HOME": "/nonexistent"}
        os.execve(sys.executable, params, env)
    except (LaunchError, trust.TrustError, custodian.CustodianError,
            OSError, ValueError, TypeError) as exc:
        print("ROOT-PINNED CUSTODIAN DENIED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
