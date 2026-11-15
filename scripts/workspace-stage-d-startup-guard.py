#!/usr/bin/env python3
"""Guarded NEXUS historical startup on a private synthetic data root.

Unlike a read-only policy check, run-synthetic *executes the exact binary FD*
only after an immutable approved-binary digest, known safe Git revision,
signed-in-code data contract and private data-tree scan all pass. The root
directory lock is inherited through exec. This is a test-only guard and is
not retroactively present in deployed historical Railway images.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys

HERE = Path(__file__).resolve().parent


def import_file(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError("NEXUS startup guard trust dependency absent")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


trust = import_file("nexus_startup_guard_trust", "workspace-trust.py")
data_screen = import_file(
    "nexus_startup_guard_schema", "workspace-stage-d-data-rollback-screen.py")

SCHEMA = "nexus.stage-d.guarded-start.v1"
FIELDS = {
    "schema", "approved_git_sha", "approved_binary_sha256",
    "data_layout", "execution_scope", "required_quarantine_support",
    "production_release_authorized",
}
KNOWN_SAFE_COMMITS = {
    "9abbc067aad3ebbb0956432cf6682d2ea70e2824",
    "f4d027bb5f7e715b298f7cf7184fa621a2fb071d",
}
BANNED_LEGACY = "588dc7672146031425b16b34956876d644244ace"
HEX = re.compile(r"(?:[0-9a-f]{2}){1,256}\Z")
MAX_FILE = 4 * 1024 * 1024
MAX_FILES = 128
MAX_TOTAL = 8 * 1024 * 1024


class StartupDenied(Exception):
    pass


def deny(reason):
    raise StartupDenied(reason)


def pin(value, label):
    if not isinstance(value, str) or not trust.SHA256_HEX.fullmatch(value):
        deny(label + " must be independently approved lowercase SHA-256")
    return value


def private_regular(fd, label, maximum):
    meta = os.fstat(fd)
    if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid()
            or meta.st_nlink != 1 or meta.st_mode & 0o077
            or meta.st_size <= 0 or meta.st_size > maximum):
        deny(label + " must be an operator-owned private regular nonlinked file")
    data = b""
    while len(data) <= maximum:
        part = os.read(fd, min(65536, maximum + 1 - len(data)))
        if not part:
            break
        data += part
    if len(data) != meta.st_size:
        deny(label + " file changed during a bounded read")
    return data


def file_descriptor(path, label):
    if not path.is_absolute() or path.is_symlink():
        deny(label + " must be an explicit absolute non-symlink path")
    flags = (os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
             | getattr(os, "O_NOFOLLOW", 0))
    fd = os.open(path, flags)
    meta = os.fstat(fd)
    visible = os.stat(path, follow_symlinks=False)
    if (meta.st_ino, meta.st_dev) != (visible.st_ino, visible.st_dev):
        os.close(fd)
        deny(label + " was replaced during open")
    return fd


def read_policy(args):
    pin(args.policy_sha256, "approval policy")
    with os.fdopen(file_descriptor(args.policy, "policy"), "rb") as stream:
        raw = private_regular(stream.fileno(), "approval policy", 8192)
    if hashlib.sha256(raw).hexdigest() != args.policy_sha256:
        deny("approval policy changed against independent exact-byte pin")
    value = trust.strict_json(raw)
    if trust.encode_json(value) != raw:
        deny("approval policy must use unique canonical bytes")
    if (not isinstance(value, dict) or set(value) != FIELDS
            or value["schema"] != SCHEMA
            or value["data_layout"] != "nexus.durable-requests.v1"
            or value["execution_scope"] != "synthetic-only"
            or value["required_quarantine_support"] is not True
            or value["production_release_authorized"] is not False):
        deny("policy is not a strict synthetic-only modern-runtime contract")
    sha = value["approved_git_sha"]
    if sha == BANNED_LEGACY:
        deny("historical recovery revision has confirmed replay/quarantine bypass")
    if sha not in KNOWN_SAFE_COMMITS:
        deny("runtime git revision unrecognized; independent compatibility proof required")
    if sha != args.runtime_git_sha:
        deny("runtime revision differs from independently pinned policy")
    pin(value["approved_binary_sha256"], "approved executable")
    if value["approved_binary_sha256"] != args.binary_sha256:
        deny("binary SHA-256 does not match independently selected policy")
    return value


def check_binary(args):
    pin(args.binary_sha256, "binary")
    fd = file_descriptor(args.binary, "gateway executable")
    try:
        raw = private_regular(fd, "gateway executable", 64 * 1024 * 1024)
        meta = os.fstat(fd)
        if not (meta.st_mode & stat.S_IXUSR) or meta.st_mode & (stat.S_ISUID | stat.S_ISGID):
            deny("gateway is not a private non-privileged executable")
        if not raw.startswith(b"\x7fELF"):
            deny("only verified native NEXUS historical ELF gateway binaries are supported")
        if hashlib.sha256(raw).hexdigest() != args.binary_sha256:
            deny("binary changed against independent approved byte digest")
        # Reposition for possible Linux fexecve; the FD must remain open
        # until the exact attested inode is executed.
        os.lseek(fd, 0, os.SEEK_SET)
        return fd
    except Exception:
        os.close(fd)
        raise


def root_file(dirfd, filename, label, max_bytes):
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(filename, flags, dir_fd=dirfd)
    with os.fdopen(fd, "rb") as stream:
        return private_regular(stream.fileno(), label, max_bytes)


def check_request_dir(parentfd):
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open("requests", flags, dir_fd=parentfd)
    try:
        meta = os.fstat(fd)
        if (meta.st_uid != os.geteuid() or meta.st_mode & 0o077
                or not stat.S_ISDIR(meta.st_mode)):
            deny("request reservation directory must be operator-owned and private")
        names = os.listdir(fd)
        if len(names) > MAX_FILES:
            deny("request reservation directory exceeds admission limit")
        for filename in names:
            if not HEX.fullmatch(filename):
                deny("unrecognized request reservation file name")
            data = root_file(fd, filename, "request reservation", 256)
            # Modern runtime treats unknown bytes as Indeterminate, not
            # safely Pending. Admit only known expected test markers.
            if data not in (b"pending\n", b"p"):
                deny("unknown reservation bytes require isolated incident review")
        if os.stat("requests", dir_fd=parentfd, follow_symlinks=False).st_ino != meta.st_ino:
            deny("request directory changed during admission")
        return len(names)
    finally:
        os.close(fd)


def check_data(root, rootfd):
    present = os.listdir(rootfd)
    if len(present) > MAX_FILES:
        deny("data directory exceeds bounded startup scanning budget")
    count, total, markers, quarantine = 0, 0, 0, False
    for filename in present:
        if filename == "requests":
            markers = check_request_dir(rootfd)
            continue
        if filename == ".nexus-recovery-required":
            content = root_file(rootfd, filename, "recovery quarantine", 2048)
            if not content.strip():
                deny("recovery quarantine marker must be nonempty")
            quarantine = True
            continue
        if not filename.endswith(".json") or not HEX.fullmatch(filename[:-5]):
            deny("unknown file in protected durable data layout")
        raw = root_file(rootfd, filename, "workspace JSON", MAX_FILE)
        count += 1
        total += len(raw)
        if total > MAX_TOTAL:
            deny("workspace JSON contents exceed startup scan limit")
        # Existing NEXUS workspace-v1 parser checks audit provenance and
        # event sequence rather than treating schema_version=1 as proof.
        data_screen.parse_workspace(filename, raw)
    visible = os.stat(root, follow_symlinks=False)
    held = os.fstat(rootfd)
    if (visible.st_dev, visible.st_ino) != (held.st_dev, held.st_ino):
        deny("durable data root changed during admission")
    return {"workspaces_checked": count, "reservations_checked": markers,
            "recovery_quarantine_present": quarantine}


def exclusive_private_root(path):
    """Operator-owned exact directory inode and fail-fast exclusive POSIX lock."""
    flags = (os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0)
             | getattr(os, "O_NOFOLLOW", 0))
    fd = os.open(path, flags)
    try:
        meta = os.fstat(fd)
        if (not stat.S_ISDIR(meta.st_mode) or meta.st_uid != os.geteuid()
                or meta.st_mode & 0o077):
            deny("synthetic data root must be owner-private")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            deny("synthetic data root is already locked by another gateway")
        visible = os.stat(path, follow_symlinks=False)
        if ((meta.st_dev, meta.st_ino) != (visible.st_dev, visible.st_ino)):
            deny("synthetic data root changed while acquiring lock")
        return fd
    except Exception:
        os.close(fd)
        raise


def admit(args):
    if os.name != "posix":
        deny("startup admission requires POSIX directory locks")
    if not args.data_dir.is_absolute():
        deny("durable data root must be an explicit absolute directory")
    contract = read_policy(args)
    binaryfd = check_binary(args)
    try:
        dirfd = exclusive_private_root(args.data_dir)
    except Exception:
        os.close(binaryfd)
        raise
    try:
        data = check_data(args.data_dir, dirfd)
        result = {
            "schema": "nexus.stage-d.guarded-start-result.v1",
            "status": "synthetic-modern-startup-admitted",
            "runtime_git_sha": contract["approved_git_sha"],
            "binary_sha256": args.binary_sha256,
            "policy_sha256": args.policy_sha256,
            "data_layout": contract["data_layout"],
            **data,
            "guard_present_in_legacy_deployed_image": False,
            "real_provider_deployment": False,
            "production_release_authorized": False,
            "release_gate": "BLOCKED",
        }
        if args.mode == "inspect":
            return result
        # The guard explicitly supports only synthetic loopback starts.
        addr = os.environ.get("NEXUS_BIND_ADDR", "")
        if not addr.startswith("127.0.0.1:") or not addr[10:].isdigit():
            deny("synthetic start must bind exclusively to IPv4 loopback")
        if not os.environ.get("NEXUS_API_TOKEN"):
            deny("ephemeral synthetic bearer token required")
        # Keep cooperative data-root flock held inside the real gateway
        # process so a second guarded launch cannot share the same root.
        os.set_inheritable(dirfd, True)
        env = dict(os.environ)
        env["NEXUS_DATA_DIR"] = str(args.data_dir)
        env["NEXUS_BOOT_LOCK_FD"] = str(dirfd)
        # Exec the *same checked inode* instead of opening a mutable path
        # again. Python/Linux supports execve(fd, ...), fail closed if not.
        if os.execve not in os.supports_fd:
            deny("FD-based executable launch unavailable; refusing path-racy exec")
        os.execve(binaryfd, [str(args.binary)], env)
        raise AssertionError("unreachable")
    finally:
        # On successful execve the descriptor survives by design, and the
        # running NEXUS process retains the directory lock until exit.
        os.close(dirfd)
        os.close(binaryfd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("inspect", "run-synthetic"))
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--binary-sha256", required=True)
    parser.add_argument("--runtime-git-sha", required=True)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--policy-sha256", required=True)
    args = parser.parse_args()
    try:
        result = admit(args)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (StartupDenied, trust.TrustError, data_screen.CompatibilityError,
            data_screen.snapshot.SnapshotError, OSError, TypeError, ValueError,
            KeyError) as exc:
        print("NEXUS STARTUP ADMISSION DENIED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
