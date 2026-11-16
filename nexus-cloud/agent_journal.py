"""Crash-conscious, single-use local execution journal for reviewed NEXUS plans.

The journal is outside workspace contents and inside a private operator-owned
root. An exclusive, fsynced claim is written *before* any plan side effect.
A crash leaves a `started` claim: re-running the same digest is denied.
This is not immutable/signed attestation or cross-host distributed consensus.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from datetime import datetime, timezone

from agent_workspace import Workspace, WorkspaceDenied

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_MAX_RECORD = 8192
_MAX_RECORDS = 1024
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK


def _record_bytes(obj: dict) -> bytes:
    data = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    if len(data) > _MAX_RECORD:
        raise WorkspaceDenied("journal-record-too-large")
    return data


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _regular(fd: int) -> None:
    st = os.fstat(fd)
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_nlink != 1
            or st.st_mode & 0o077 or st.st_size > _MAX_RECORD):
        raise WorkspaceDenied("journal-record-unsafe")


class ApprovalJournal:
    """All calls are made while holding the workspace's operation_lock."""

    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.name = f".nexus-agent-{workspace.name}.journal"

    def _directory(self, *, create: bool = False) -> int:
        rootfd = os.open(self.workspace.root, _DIR_FLAGS)
        try:
            rootstat = os.fstat(rootfd)
            if (not stat.S_ISDIR(rootstat.st_mode) or rootstat.st_uid != os.getuid()
                    or rootstat.st_mode & 0o077):
                raise WorkspaceDenied("unsafe-journal-root")
            if create:
                try:
                    os.mkdir(self.name, mode=0o700, dir_fd=rootfd)
                    os.fsync(rootfd)
                except FileExistsError:
                    pass
            fd = os.open(self.name, _DIR_FLAGS, dir_fd=rootfd)
        finally:
            os.close(rootfd)
        st = os.fstat(fd)
        if (not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid()
                or st.st_mode & 0o077):
            os.close(fd)
            raise WorkspaceDenied("unsafe-journal-directory")
        return fd

    @staticmethod
    def _name(digest: str) -> str:
        if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
            raise WorkspaceDenied("invalid-journal-digest")
        return digest + ".json"

    def read(self, digest: str) -> dict:
        name = self._name(digest)
        fd = self._directory()
        try:
            filefd = os.open(name, _FILE_FLAGS, dir_fd=fd)
            try:
                _regular(filefd)
                content = os.read(filefd, _MAX_RECORD + 1)
                if len(content) > _MAX_RECORD:
                    raise WorkspaceDenied("journal-record-too-large")
            finally:
                os.close(filefd)
        finally:
            os.close(fd)
        try:
            obj = json.loads(content)
        except (UnicodeError, ValueError) as exc:
            raise WorkspaceDenied("journal-record-corrupt") from exc
        if (not isinstance(obj, dict) or obj.get("plan_sha256") != digest
                or obj.get("workspace") != self.workspace.name
                or obj.get("state") not in ("started", "finished")
                or obj.get("schema") != 1):
            raise WorkspaceDenied("journal-record-corrupt")
        return obj

    def claim(self, digest: str, *, version: int, workspace_before: str,
              execution_nonce: str | None) -> dict:
        name = self._name(digest)
        record = {"schema": 1, "state": "started", "plan_sha256": digest,
                  "workspace": self.workspace.name, "plan_version": version,
                  "execution_nonce": execution_nonce,
                  "workspace_sha256_before": workspace_before, "started_utc": _utc()}
        data = _record_bytes(record)
        dirfd = self._directory(create=True)
        try:
            # Limit persistent claims; never silently prune approval evidence.
            if len(os.listdir(dirfd)) >= _MAX_RECORDS:
                raise WorkspaceDenied("journal-capacity-reached")
            try:
                fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                             os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=dirfd)
            except FileExistsError as exc:
                raise WorkspaceDenied("approval-already-consumed") from exc
            try:
                _regular(fd)
                with os.fdopen(fd, "wb", closefd=False) as stream:
                    stream.write(data)
                    stream.flush()
                os.fsync(fd)
            finally:
                os.close(fd)
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
        return record

    def finish(self, digest: str, *, status: str, workspace_after: str | None,
               completed_steps: int, step_summaries: list[dict]) -> dict:
        # Check the existing claim belongs to this exact workspace and digest.
        previous = self.read(digest)
        if previous["state"] != "started":
            raise WorkspaceDenied("journal-already-finished")
        record = {**previous, "state": "finished", "finished_utc": _utc(),
                  "result": status, "workspace_sha256_after": workspace_after,
                  "completed_steps": completed_steps, "steps": step_summaries}
        data = _record_bytes(record)
        dirfd = self._directory()
        tmpname = ".nexus-journal-write-" + os.urandom(12).hex()
        try:
            tmpfd = os.open(tmpname, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                            os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=dirfd)
            try:
                _regular(tmpfd)
                with os.fdopen(tmpfd, "wb", closefd=False) as stream:
                    stream.write(data)
                    stream.flush()
                os.fsync(tmpfd)
            finally:
                os.close(tmpfd)
            try:
                # Journal directory is owned/private and the workspace lock is held.
                os.replace(tmpname, self._name(digest), src_dir_fd=dirfd, dst_dir_fd=dirfd)
                os.fsync(dirfd)
            finally:
                try:
                    os.unlink(tmpname, dir_fd=dirfd)
                except FileNotFoundError:
                    pass
        finally:
            os.close(dirfd)
        return record
