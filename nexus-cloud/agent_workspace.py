"""Opt-in local NEXUS engineering workspace.

This is deliberately NOT imported into the public API adapter or called by an LLM.
A trusted local operator grants each operation and chooses a digest-pinned image.
The Docker daemon is a separate privileged trust boundary.
"""

from __future__ import annotations

import os
import re
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
    if any(p in ("", ".", "..") or len(p.encode("utf-8")) > 128 for p in parts):
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
    if shutil.which(docker_executable) is None:
        raise WorkspaceDenied("docker-unavailable")
    with tempfile.TemporaryDirectory(prefix="nexus-agent-cid-") as temp:
        cidfile = os.path.join(temp, "cid")
        args = [docker_executable, "run", "--rm", "--pull", "never", "--cidfile", cidfile,
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
                    proc.wait(timeout=max(0.1, timeout_seconds - (time.monotonic() - start)))
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
