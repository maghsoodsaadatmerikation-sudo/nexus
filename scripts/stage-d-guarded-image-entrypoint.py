#!/usr/bin/env python3
"""Mandatory *default image entrypoint* for synthetic-only guarded NEXUS.

The OCI image configuration selects this program, not the gateway. A person
with Docker daemon or orchestrator authority may override ENTRYPOINT:
this is not an unbypassable security control against such an administrator.
"""
import os
from pathlib import Path
import stat
import sys


def deny(reason):
    print("NEXUS GUARDED IMAGE BOOT DENIED: " + reason, file=sys.stderr)
    return 70


def main():
    if len(sys.argv) != 1:
        return deny("image entrypoint does not accept user command overrides")
    if os.name != "posix" or os.geteuid() != 10001:
        return deny("synthetic image must start as unprivileged uid 10001")
    root = Path("/data")
    if root.is_symlink() or not root.is_dir() or not os.path.ismount(root):
        return deny("synthetic private data must be a separately mounted /data directory")
    meta = root.stat()
    if (not stat.S_ISDIR(meta.st_mode)
            or meta.st_uid != os.geteuid()
            or meta.st_mode & 0o077):
        return deny("/data must belong to the unprivileged owner and be private (0700)")
    values = {}
    for name in ("NEXUS_POLICY_SHA256", "NEXUS_BINARY_SHA256",
                 "NEXUS_APPROVED_GIT_SHA", "NEXUS_BIND_ADDR", "NEXUS_API_TOKEN"):
        value = os.environ.get(name, "")
        if not value or len(value) > 512:
            return deny("missing or excessive synthetic launch value: " + name)
        values[name] = value
    if not values["NEXUS_BIND_ADDR"].startswith("127.0.0.1:"):
        return deny("this image may bind only to IPv4 loopback")
    if not values["NEXUS_BIND_ADDR"][10:].isdigit():
        return deny("invalid loopback port")
    port = int(values["NEXUS_BIND_ADDR"][10:])
    if not 1024 <= port <= 65535:
        return deny("synthetic test port outside approved unprivileged range")
    if len(values["NEXUS_API_TOKEN"]) < 24:
        return deny("synthetic bearer token is too short")

    # Minimal environment, no Python import/loader overrides or untrusted
    # inherited application settings. The inner guard will open and pin the
    # exact binary and independently approved policy itself.
    environment = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": "/opt/nexus",
        "PYTHONDONTWRITEBYTECODE": "1",
        "NEXUS_BIND_ADDR": values["NEXUS_BIND_ADDR"],
        "NEXUS_API_TOKEN": values["NEXUS_API_TOKEN"],
    }
    argv = [
        "/usr/local/bin/python3", "-I", "-B",
        "/opt/nexus/workspace-stage-d-startup-guard.py",
        "run-synthetic",
        "--data-dir", "/data",
        "--binary", "/opt/nexus/nexus",
        "--binary-sha256", values["NEXUS_BINARY_SHA256"],
        "--runtime-git-sha", values["NEXUS_APPROVED_GIT_SHA"],
        "--policy", "/run/nexus/approval.json",
        "--policy-sha256", values["NEXUS_POLICY_SHA256"],
    ]
    os.execve("/usr/local/bin/python3", argv, environment)
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
