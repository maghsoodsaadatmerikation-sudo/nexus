"""Optional per-host durable request counter for NEXUS's model gateway.

This is deliberately an *attempt count*, never money or model quality.
All callers sharing one private directory are serialized on its Linux flock.
Never reset or refund a slot after attempted dispatch; the provider may bill
even if the gateway fails or the browser disconnects.

A provider account-level quota remains necessary across hosts/replicas and for
protection against credential use outside NEXUS.
"""
from __future__ import annotations

import fcntl
import os
import secrets
import stat
from threading import Lock

COUNTER_NAME = "model-attempts.counter"
MAX_COUNTER = 4096


class UnavailableModelRequestBudget:
    """Safe fallback when the explicitly configured state volume is unusable."""

    scope = "durable_store_unavailable"

    def __init__(self, limit: int):
        self.limit = limit

    def reserve(self) -> bool:
        return False

    def snapshot(self) -> dict:
        return {"limit": self.limit, "attempted": None, "remaining": 0}

    def close(self) -> None:
        pass


class DurableModelRequestBudget:
    """Cross-worker on one Linux host, crash-safe atomic replacement + fsync.

    The operator must supply an existing, owner-private, non-symlink directory.
    A stable advisory flock on that directory serializes reads and replacements.
    The counter file is owner-private, regular, and never opened through a link.
    An I/O error, modified directory, malformed count or lost volume fails
    closed; nothing in this class can clear a committed counter.
    """

    scope = "one_private_host_directory_until_explicit_reset"

    def __init__(self, directory: str, limit: int):
        if (not isinstance(directory, str) or not directory
            or not os.path.isabs(directory)
            or "\x00" in directory
            or not isinstance(limit, int) or not 0 <= limit <= MAX_COUNTER):
            raise ValueError("invalid local quota configuration")
        self.directory = directory
        self.limit = limit
        self._lock = Lock()
        self._fd = os.open(
            directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        )
        try:
            directory_stat = os.fstat(self._fd)
            if (not stat.S_ISDIR(directory_stat.st_mode)
                or directory_stat.st_uid != os.getuid()
                or directory_stat.st_mode & 0o077):
                raise PermissionError("private model quota directory required")
            self._identity = (directory_stat.st_dev, directory_stat.st_ino)
        except BaseException:
            os.close(self._fd)
            raise

    def _check_directory(self) -> None:
        current = os.stat(self.directory, follow_symlinks=False)
        fd_stat = os.fstat(self._fd)
        if (not stat.S_ISDIR(current.st_mode)
            or (current.st_dev, current.st_ino) != self._identity
            or (fd_stat.st_dev, fd_stat.st_ino) != self._identity
            or current.st_uid != os.getuid()
            or current.st_mode & 0o077
            or fd_stat.st_nlink == 0):
            raise PermissionError("model quota directory was replaced or exposed")

    def _read_locked(self) -> int:
        try:
            # A corrupt FIFO must not block before the regular-file check.
            fd = os.open(COUNTER_NAME, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
                         | os.O_NONBLOCK, dir_fd=self._fd)
        except FileNotFoundError:
            return 0
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or info.st_nlink != 1):
                raise PermissionError("model quota file is not private")
            raw = os.read(fd, 32)
        finally:
            os.close(fd)
        if (not raw.endswith(b"\n") or len(raw) > 6
            or not raw[:-1].isascii() or not raw[:-1].isdigit()):
            raise ValueError("invalid durable model quota count")
        value = int(raw[:-1])
        if value > MAX_COUNTER:
            raise ValueError("durable model quota count overflow")
        return value

    def _commit_locked(self, attempted: int) -> None:
        name = ".model-attempts-" + secrets.token_hex(12) + ".tmp"
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                     os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=self._fd)
        try:
            encoded = (str(attempted) + "\n").encode("ascii")
            if os.write(fd, encoded) != len(encoded):
                raise OSError("short durable quota write")
            os.fsync(fd)
        except BaseException:
            os.close(fd)
            try:
                os.unlink(name, dir_fd=self._fd)
            except OSError:
                pass
            raise
        else:
            os.close(fd)
        try:
            os.replace(name, COUNTER_NAME,
                       src_dir_fd=self._fd, dst_dir_fd=self._fd)
            os.fsync(self._fd)  # Commit directory rename across a power loss.
        finally:
            # If replace completed, the old name does not exist.
            try:
                os.unlink(name, dir_fd=self._fd)
            except FileNotFoundError:
                pass

    def _transaction(self, *, consume: bool) -> tuple[dict, bool]:
        with self._lock:
            fcntl.flock(self._fd, fcntl.LOCK_EX)
            try:
                self._check_directory()
                current = self._read_locked()
                reserved = consume and current < self.limit
                if reserved:
                    # One critical section covers read, admission, persist,
                    # and durable fsync. A competing worker cannot overdraw.
                    self._commit_locked(current + 1)
                    current += 1
                return ({"limit": self.limit, "attempted": current,
                         "remaining": max(0, self.limit - current)}, reserved)
            finally:
                fcntl.flock(self._fd, fcntl.LOCK_UN)

    def reserve(self) -> bool:
        try:
            _, reserved = self._transaction(consume=True)
            return reserved
        except (OSError, ValueError, TypeError):
            return False

    def snapshot(self) -> dict:
        try:
            values, _ = self._transaction(consume=False)
            return values
        except (OSError, ValueError, TypeError):
            return {"limit": self.limit, "attempted": None, "remaining": 0}

    def close(self) -> None:
        with self._lock:
            if self._fd >= 0:
                os.close(self._fd)
                self._fd = -1
