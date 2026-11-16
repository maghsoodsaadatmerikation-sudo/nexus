"""Opt-in local NEXUS engineering workspace.

This is deliberately NOT imported into the public API adapter or called by an LLM.
A trusted local operator grants each operation and chooses a digest-pinned image.
The Docker daemon is a separate privileged trust boundary.
"""

from __future__ import annotations

import os
import re
import hashlib
import json
import difflib
import fcntl
from contextlib import contextmanager
import selectors
import shutil
import stat
import subprocess
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path


MAX_FILE_BYTES = 1_048_576
MAX_OUTPUT_BYTES = 262_144
MAX_ARCHIVE_BYTES = 20 * 1_048_576
MAX_ARCHIVE_FILES = 200
MAX_COMMAND_ARGS = 64
MAX_COMMAND_BYTES = 16_384
IMAGE_DIGEST = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:/-]*@sha256:[0-9a-f]{64}$")
WORKSPACE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,47}$")


class WorkspaceDenied(ValueError):
    """An operation fails an explicit NEXUS workspace boundary."""


def safe_parts(path: str) -> tuple[str, ...]:
    if not isinstance(path, str) or len(path) > 512 or not path or "\\" in path or "\x00" in path:
        raise WorkspaceDenied("invalid-path")
    parts = tuple(path.split("/"))
    try:
        invalid = any(p in ("", ".", "..") or len(p.encode("utf-8")) > 128 for p in parts)
    except UnicodeError as exc:
        raise WorkspaceDenied("invalid-path-encoding") from exc
    if invalid:
        raise WorkspaceDenied("invalid-path")
    return parts


class Workspace:
    """File operations use dirfds/O_NOFOLLOW instead of path-prefix checks."""

    def __init__(self, root: str | Path, name: str):
        if not WORKSPACE_ID.fullmatch(name):
            raise WorkspaceDenied("invalid-workspace-id")
        root = Path(root)
        if not root.is_absolute() or root.is_symlink() or any(c in str(root) for c in ",\n\r"):
            raise WorkspaceDenied("root-must-be-absolute-directory-not-symlink")
        root_stat = root.stat()
        if not stat.S_ISDIR(root_stat.st_mode) or root_stat.st_uid != os.getuid() or root_stat.st_mode & 0o077:
            raise WorkspaceDenied("root-must-be-private-owned-directory")
        self.root = root
        self.name = name
        try:
            (root / name).mkdir(mode=0o700)
        except FileExistsError:
            pass
        self.path = root / name
        st = self.path.lstat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
            raise WorkspaceDenied("workspace-must-be-private-owned-directory")

    @contextmanager
    def operation_lock(self, *, timeout_seconds: float = 3.0):
        """Advisory cross-process lock covering plan admission and all its steps.

        The persistent lock inode is stored OUTSIDE the manifest-hashed project
        directory so merely reviewing or executing a plan does not change the
        manifest. All official local CLI commands honor this lock. This does not
        prevent an unrelated host process or Docker container from writing to
        the filesystem: the operator must dedicate the host account/workspace.
        """
        if type(timeout_seconds) not in (float, int) or not 0 <= timeout_seconds <= 30:
            raise WorkspaceDenied("invalid-lock-timeout")
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        rootfd = os.open(self.root, flags)
        fd = None
        try:
            st = os.fstat(rootfd)
            if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
                raise WorkspaceDenied("unsafe-workspace-root")
            # O_NOFOLLOW and the private root block replacement of the lock
            # with a link to a sensitive filesystem object.
            fd = os.open(f".nexus-agent-{self.name}.lock",
                         os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC,
                         0o600, dir_fd=rootfd)
            lockstat = os.fstat(fd)
            if (not stat.S_ISREG(lockstat.st_mode) or lockstat.st_uid != os.getuid()
                    or lockstat.st_nlink != 1 or lockstat.st_mode & 0o077):
                raise WorkspaceDenied("unsafe-workspace-lock")
        except BaseException:
            if fd is not None:
                os.close(fd)
            raise
        finally:
            os.close(rootfd)
        assert fd is not None
        acquired = False
        try:
            deadline = time.monotonic() + timeout_seconds
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                    break
                except BlockingIOError as exc:
                    if time.monotonic() >= deadline:
                        raise WorkspaceDenied("workspace-busy") from exc
                    time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
            yield
        finally:
            if acquired:
                fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _parent(self, path: str, *, create: bool = False) -> tuple[int, str]:
        parts = safe_parts(path)
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        fd = os.open(self.path, flags)
        try:
            for part in parts[:-1]:
                if create:
                    try:
                        os.mkdir(part, 0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                child = os.open(part, flags, dir_fd=fd)
                os.close(fd)
                fd = child
            return fd, parts[-1]
        except BaseException:
            os.close(fd)
            raise

    def read(self, path: str) -> bytes:
        fd, leaf = self._parent(path)
        try:
            filefd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=fd)
            try:
                st = os.fstat(filefd)
                if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_FILE_BYTES or st.st_nlink != 1:
                    raise WorkspaceDenied("not-a-bounded-private-regular-file")
                content = bytearray()
                while len(content) <= MAX_FILE_BYTES:
                    chunk = os.read(filefd, min(65_536, MAX_FILE_BYTES + 1 - len(content)))
                    if not chunk:
                        return bytes(content)
                    content.extend(chunk)
                raise WorkspaceDenied("file-too-large")
            finally:
                os.close(filefd)
        finally:
            os.close(fd)

    def write(self, path: str, data: bytes, *, create_parents: bool = False) -> None:
        if not isinstance(data, bytes) or len(data) > MAX_FILE_BYTES:
            raise WorkspaceDenied("file-too-large-or-not-bytes")
        fd, leaf = self._parent(path, create=create_parents)
        tmp = None
        temp_name = None
        try:
            try:
                st = os.stat(leaf, dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                st = None
            if st is not None and (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1):
                raise WorkspaceDenied("existing-file-is-not-private-regular-file")
            # Randomly named, exclusive, no-follow sibling. Atomic rename on success.
            for _ in range(5):
                name = ".nexus-write-" + os.urandom(12).hex()
                try:
                    tmp = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=fd)
                    temp_name = name
                    break
                except FileExistsError:
                    continue
            if tmp is None:
                raise WorkspaceDenied("temporary-file-collision")
            with os.fdopen(tmp, "wb", closefd=True) as stream:
                tmp = None
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, leaf, src_dir_fd=fd, dst_dir_fd=fd)
            temp_name = None
            os.fsync(fd)
        finally:
            if tmp is not None:
                os.close(tmp)
            if temp_name is not None:
                try:
                    os.unlink(temp_name, dir_fd=fd)
                except FileNotFoundError:
                    pass
            os.close(fd)

    def edit(self, path: str, old: bytes, new: bytes) -> None:
        if not old or not isinstance(old, bytes) or not isinstance(new, bytes):
            raise WorkspaceDenied("invalid-exact-edit")
        original = self.read(path)
        if original.count(old) != 1:
            raise WorkspaceDenied("edit-requires-exactly-one-match")
        self.write(path, original.replace(old, new, 1))

    def manifest(self) -> dict[str, object]:
        """Deterministic content identity for a bounded private workspace.

        Hashes every file, including dotfiles, and records empty directories.
        The returned digest identifies a snapshot observation, not a lock on
        future filesystem changes. Symlinks, hardlinks and special files fail
        closed rather than being silently skipped.
        """
        files = []
        directories = []
        total_bytes = 0
        total_entries = 0
        for current, subdirs, names in os.walk(self.path, topdown=True, followlinks=False):
            subdirs.sort()
            names.sort()
            for name in subdirs + names:
                full = Path(current) / name
                stat_result = full.lstat()
                if stat.S_ISLNK(stat_result.st_mode) or not (
                    stat.S_ISDIR(stat_result.st_mode) or stat.S_ISREG(stat_result.st_mode)
                ):
                    raise WorkspaceDenied("manifest-rejects-links-and-special-files")
                rel = full.relative_to(self.path).as_posix()
                safe_parts(rel)
                total_entries += 1
                if total_entries > 400:
                    raise WorkspaceDenied("manifest-entry-limit")
                if stat.S_ISDIR(stat_result.st_mode):
                    directories.append(rel)
                else:
                    if stat_result.st_nlink != 1 or stat_result.st_size > MAX_FILE_BYTES:
                        raise WorkspaceDenied("manifest-rejects-hardlinks-and-large-files")
                    total_bytes += stat_result.st_size
                    if len(files) >= MAX_ARCHIVE_FILES or total_bytes > MAX_ARCHIVE_BYTES:
                        raise WorkspaceDenied("manifest-size-limit")
                    data = self.read(rel)
                    files.append({"path": rel, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        state = {"version": 1, "directories": sorted(directories), "files": sorted(files, key=lambda row: row["path"])}
        canonical = json.dumps(state, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("ascii")
        return {"workspace": self.name, "sha256": hashlib.sha256(canonical).hexdigest(),
                "file_count": len(files), "directory_count": len(directories), "total_bytes": total_bytes,
                "files": state["files"], "directories": state["directories"]}

    def search(self, query: str, *, case_sensitive: bool = False) -> dict[str, object]:
        """Bounded literal cross-file search, returning inert user-reviewable excerpts.

        No regex execution, symlink following, shell commands, network or model.
        Binary/non-UTF-8 documents are not interpreted as code or text.
        """
        if not isinstance(query, str) or not query or len(query) > 128 or "\x00" in query or "\n" in query or "\r" in query:
            raise WorkspaceDenied("invalid-search-query")
        if type(case_sensitive) is not bool:
            raise WorkspaceDenied("invalid-search-mode")
        observed = self.manifest()
        matches: list[dict[str, object]] = []
        scanned = 0
        skipped = 0
        truncated = False
        term = query if case_sensitive else query.casefold()
        for entry in observed["files"]:
            raw = self.read(entry["path"])
            try:
                content = raw.decode("utf-8")
            except UnicodeError:
                skipped += 1
                continue
            if "\x00" in content:
                skipped += 1
                continue
            scanned += 1
            for number, line in enumerate(content.splitlines(), 1):
                haystack = line if case_sensitive else line.casefold()
                if term not in haystack:
                    continue
                if len(matches) >= 50:
                    truncated = True
                    break
                matches.append({"path": entry["path"], "line": number, "excerpt": line[:180]})
            if truncated:
                break
        return {"query": query, "matches": matches, "match_count": len(matches),
                "scanned_files": scanned, "skipped_binary_files": skipped,
                "truncated": truncated, "workspace_sha256_at_scan_start": observed["sha256"]}

    def preview_edit(self, path: str, old: bytes, new: bytes) -> dict[str, object]:
        """Show an exact-one-match code patch without modifying any file."""
        if not isinstance(old, bytes) or not old or not isinstance(new, bytes) or len(old) > MAX_FILE_BYTES or len(new) > MAX_FILE_BYTES:
            raise WorkspaceDenied("invalid-exact-edit")
        original = self.read(path)
        if original.count(old) != 1:
            raise WorkspaceDenied("edit-requires-exactly-one-match")
        proposed = original.replace(old, new, 1)
        if len(proposed) > MAX_FILE_BYTES:
            raise WorkspaceDenied("file-too-large")
        try:
            before_lines = original.decode("utf-8").splitlines(keepends=True)
            after_lines = proposed.decode("utf-8").splitlines(keepends=True)
        except UnicodeError as exc:
            raise WorkspaceDenied("preview-requires-utf8-text") from exc
        # An adversarial giant text file should not cause quadratic diff work.
        if len(original) > 131_072 or len(proposed) > 131_072 or len(before_lines) > 2_000 or len(after_lines) > 2_000:
            raise WorkspaceDenied("preview-line-limit")
        diff = "".join(difflib.unified_diff(before_lines, after_lines,
                   fromfile="a/" + path, tofile="b/" + path, n=3))
        if len(diff.encode("utf-8")) > 32_768:
            raise WorkspaceDenied("preview-diff-limit")
        return {"path": path, "old_sha256": hashlib.sha256(original).hexdigest(),
                "proposed_sha256": hashlib.sha256(proposed).hexdigest(),
                "proposed_bytes": len(proposed), "diff": diff, "applied": False}

    def package(self, destination: str | Path) -> dict[str, int]:
        dest = Path(destination)
        if not dest.is_absolute() or dest.is_symlink() or dest.exists():
            raise WorkspaceDenied("archive-destination-must-be-new-absolute-file")
        # The host path is selected by the local operator; never include the ZIP itself.
        if dest.resolve().is_relative_to(self.path.resolve()):
            raise WorkspaceDenied("archive-destination-inside-workspace")
        paths: list[str] = []
        total = 0
        for current, directories, files in os.walk(self.path, topdown=True, followlinks=False):
            for item in directories + files:
                full = Path(current) / item
                st = full.lstat()
                if stat.S_ISLNK(st.st_mode) or (not stat.S_ISDIR(st.st_mode) and not stat.S_ISREG(st.st_mode)):
                    raise WorkspaceDenied("archive-rejects-links-and-special-files")
                if stat.S_ISREG(st.st_mode) and st.st_nlink != 1:
                    raise WorkspaceDenied("archive-rejects-hardlinks")
            for item in files:
                rel = (Path(current) / item).relative_to(self.path).as_posix()
                size = (Path(current) / item).lstat().st_size
                total += size
                if size > MAX_FILE_BYTES or total > MAX_ARCHIVE_BYTES or len(paths) >= MAX_ARCHIVE_FILES:
                    raise WorkspaceDenied("archive-limit")
                paths.append(rel)
        # Read through the same symlink-resistant path operations; zip content is inert.
        try:
            with zipfile.ZipFile(dest, mode="x", compression=zipfile.ZIP_DEFLATED) as archive:
                for rel in sorted(paths):
                    archive.writestr(rel, self.read(rel))
        except BaseException:
            dest.unlink(missing_ok=True)
            raise
        return {"files": len(paths), "input_bytes": total, "archive_bytes": dest.stat().st_size}


@dataclass(frozen=True)
class RunResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    status: str


def run_container(
    workspace: Workspace, image: str, command: list[str], *,
    approved: bool, timeout_seconds: int = 30, docker_executable: str = "docker",
    cancel_event=None,
) -> RunResult:
    """Execute an approved foreground command in a Docker daemon sandbox.

    No network mode switch, daemon socket or secrets passthrough is provided.
    Real safety depends on the operator's Docker host and image provenance.
    """
    if not approved:
        raise WorkspaceDenied("execution-requires-explicit-approval")
    if not IMAGE_DIGEST.fullmatch(image):
        raise WorkspaceDenied("image-must-be-digest-pinned")
    if not isinstance(command, list) or not command or len(command) > MAX_COMMAND_ARGS or any(
        not isinstance(a, str) or not a or "\x00" in a for a in command
    ) or sum(len(a.encode("utf-8")) for a in command) > MAX_COMMAND_BYTES:
        raise WorkspaceDenied("invalid-command-argv")
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 120:
        raise WorkspaceDenied("invalid-timeout")
    if os.name != "posix" or os.getuid() == 0:
        raise WorkspaceDenied("run-requires-unprivileged-linux-host-user")
    if cancel_event is not None and cancel_event.is_set():
        return RunResult(-1, "", "", 0, "cancelled")
    if shutil.which(docker_executable) is None:
        raise WorkspaceDenied("docker-unavailable")
    with tempfile.TemporaryDirectory(prefix="nexus-agent-cid-") as temp:
        cidfile = os.path.join(temp, "cid")
        args = [docker_executable, "run", "--rm", "--pull", "never", "--cidfile", cidfile,
                "--label", "nexus.operator.managed=1",
                 "--network", "none", "--ipc", "none", "--read-only", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges", "--pids-limit", "64",
                "--memory", "256m", "--cpus", "1", "--ulimit", "nofile=128:128",
                "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=64m",
                "--user", f"{os.getuid()}:{os.getgid()}", "--workdir", "/workspace",
                "--mount", f"type=bind,source={workspace.path},target=/workspace",
                image, *command]
        start = time.monotonic()
        proc = None
        stdout, stderr = bytearray(), bytearray()
        status = "complete"
        try:
            proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, close_fds=True, env={"PATH": os.environ.get("PATH", "")})
            sel = selectors.DefaultSelector()
            try:
                for pipe, target in ((proc.stdout, stdout), (proc.stderr, stderr)):
                    os.set_blocking(pipe.fileno(), False)
                    sel.register(pipe, selectors.EVENT_READ, target)
                while sel.get_map():
                    if cancel_event is not None and cancel_event.is_set():
                        status = "cancelled"
                        break
                    remaining = timeout_seconds - (time.monotonic() - start)
                    if remaining <= 0:
                        status = "timeout"
                        break
                    for key, _ in sel.select(min(0.2, remaining)):
                        chunk = os.read(key.fileobj.fileno(), 65_536)
                        if not chunk:
                            sel.unregister(key.fileobj)
                        else:
                            key.data.extend(chunk)
                            if len(stdout) + len(stderr) > MAX_OUTPUT_BYTES:
                                status = "output-limit"
                                break
                    if status != "complete":
                        break
                if status == "complete":
                    # Do not block in wait() without checking external cancel.
                    # A process may have closed its pipes and remained alive.
                    while proc.poll() is None:
                        if cancel_event is not None and cancel_event.is_set():
                            status = "cancelled"
                            break
                        if time.monotonic() - start >= timeout_seconds:
                            status = "timeout"
                            break
                        time.sleep(0.05)
            except subprocess.TimeoutExpired:
                status = "timeout"
            finally:
                sel.close()
            if status != "complete":
                proc.kill()
                proc.wait(timeout=3)
            code = proc.returncode if status == "complete" else -1
        finally:
            if proc is not None and proc.poll() is None:
                proc.kill()
                proc.wait(timeout=3)
            # The Docker CLI can die while its container survives; explicit cleanup.
            if os.path.isfile(cidfile):
                cid = Path(cidfile).read_text().strip()
                if re.fullmatch(r"[0-9a-f]{64}", cid):
                    try:
                        subprocess.run([docker_executable, "rm", "-f", cid], timeout=5,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                    except (OSError, subprocess.TimeoutExpired):
                        pass
        return RunResult(code, stdout[:MAX_OUTPUT_BYTES].decode("utf-8", "replace"),
                         stderr[:MAX_OUTPUT_BYTES].decode("utf-8", "replace"),
                         int((time.monotonic() - start) * 1000), status)
