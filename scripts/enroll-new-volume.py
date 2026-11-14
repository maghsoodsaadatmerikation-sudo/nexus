#!/usr/bin/env python3
"""Explicit OFFLINE enrollment of a provably empty new NEXUS data directory.

Never run against production, recovered, or previously populated volumes.
For existing data, require a separate independently reviewed offline migration
and verified full-volume backup; this utility deliberately refuses adoption.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import stat
import sys

MARKER = ".nexus-volume-identity"
PREFIX = b"nexus.volume-identity.v1\n"
ACK = "I AM INITIALIZING A NEW EMPTY NEXUS DATA VOLUME"


def enroll(root: Path, volume_id: str, *, offline: bool, confirmation: str) -> None:
    if not offline or confirmation != ACK:
        raise ValueError("explicit offline new-volume confirmation required")
    if re.fullmatch("[0-9a-f]{32}", volume_id) is None:
        raise ValueError("invalid volume identity")
    if root.is_symlink():
        raise ValueError("symlink data volume rejected")
    before = os.stat(root, follow_symlinks=False)
    if not stat.S_ISDIR(before.st_mode):
        raise ValueError("expected existing physical directory")
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise ValueError("data volume root changed")
        if os.listdir(fd):
            raise ValueError("nonempty volume refused; backup and independent migration required")
        # Exclusive no-follow create relative to pinned directory descriptor.
        marker = os.open(
            MARKER, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600, dir_fd=fd,
        )
        ok = False
        try:
            data = PREFIX + volume_id.encode("ascii") + b"\n"
            sent = 0
            while sent < len(data):
                written = os.write(marker, data[sent:])
                if written <= 0:
                    raise OSError("short marker write")
                sent += written
            os.fsync(marker)
            ok = True
        finally:
            os.close(marker)
            if not ok:
                os.unlink(MARKER, dir_fd=fd)
        os.fsync(fd)
        after = os.stat(root, follow_symlinks=False)
        if not stat.S_ISDIR(after.st_mode) or (
            after.st_dev, after.st_ino
        ) != (opened.st_dev, opened.st_ino):
            raise ValueError("data volume changed during enrollment")
    finally:
        os.close(fd)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--volume-id", required=True)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    try:
        enroll(args.directory, args.volume_id, offline=args.offline, confirmation=args.confirm)
    except (OSError, ValueError, UnicodeError):
        print("NEXUS NEW VOLUME ENROLLMENT: REFUSED (no implicit adoption)", file=sys.stderr)
        return 1
    print("NEXUS NEW VOLUME ENROLLMENT: SUCCESS (new empty directory only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
