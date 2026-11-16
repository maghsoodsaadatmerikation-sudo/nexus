"""Operator-root-wide, fail-closed journal census and read-only Docker inventory.

The census is local to one private root and Linux UID, NOT a host-wide process
attestation or a clearance mechanism. The Docker query is observational only;
containers without the new NEXUS label or on another daemon may be invisible.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import time

from agent_workspace import WORKSPACE_ID, Workspace, WorkspaceDenied

HOST_LOCK_NAME = '.nexus-agent-host-admission.lock'
MAX_WORKSPACES = 128
MAX_MANAGED_CONTAINERS = 256
_JOURNAL = re.compile(r'^\.nexus-agent-(.+)\.journal$')
_SHA256 = re.compile(r'^[0-9a-f]{64}$')
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def _verified_root(root: str | Path) -> tuple[Path, int]:
    path = Path(root)
    if not path.is_absolute() or '..' in path.parts or path.is_symlink():
        raise WorkspaceDenied('host-census-unsafe-root')
    fd = os.open('/', _DIR_FLAGS)
    try:
        for component in path.parts[1:]:
            next_fd = os.open(component, _DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        st = os.fstat(fd)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
            raise WorkspaceDenied('host-census-unsafe-root')
        return path, fd
    except BaseException:
        os.close(fd)
        raise


@contextmanager
def admission_lock(root: str | Path):
    """Serialize ALL official single-use claims under an operator private root.

    Called while holding the chosen workspace operation lock, never from
    journal.finish(), so cross-workspace concurrent claims cannot both pass a
    'clear' census. A crash releases flock, not the durable STARTED record.
    """
    _, dfd = _verified_root(root)
    fd = None
    acquired = False
    try:
        fd = os.open(HOST_LOCK_NAME, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW |
                     os.O_CLOEXEC, 0o600, dir_fd=dfd)
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_nlink != 1 or st.st_mode & 0o077:
            raise WorkspaceDenied('host-admission-lock-unsafe')
        deadline = time.monotonic() + 3
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise WorkspaceDenied('host-admission-busy')
                time.sleep(.02)
        yield
    finally:
        if fd is not None:
            if acquired:
                fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        os.close(dfd)


def journal_census(root: str | Path) -> dict:
    """Check every journal in one root; never amend or clear records."""
    path, dfd = _verified_root(root)
    try:
        names = os.listdir(dfd)
        journals = []
        for entry in names:
            if not (entry.startswith('.nexus-agent-') and entry.endswith('.journal')):
                continue
            found = _JOURNAL.fullmatch(entry)
            if not found or not WORKSPACE_ID.fullmatch(found.group(1)):
                raise WorkspaceDenied('host-census-unknown-journal')
            journals.append((entry, found.group(1)))
        if len(journals) > MAX_WORKSPACES:
            raise WorkspaceDenied('host-census-capacity')
        from agent_journal import ApprovalJournal  # avoid import cycle
        finished = 0
        pending = []
        for entry, name in sorted(journals):
            st = os.stat(entry, dir_fd=dfd, follow_symlinks=False)
            if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
                raise WorkspaceDenied('host-census-journal-unsafe')
            wst = os.stat(name, dir_fd=dfd, follow_symlinks=False)
            if not stat.S_ISDIR(wst.st_mode) or wst.st_uid != os.getuid() or wst.st_mode & 0o077:
                raise WorkspaceDenied('host-census-workspace-unsafe')
            # Only an existing verified workspace is constructed. No new
            # workspace, external process or journal is ever created here.
            report = ApprovalJournal(Workspace(path, name)).audit()
            finished += report['finished_count']
            for digest in report['unfinished_digests']:
                pending.append({'workspace': name, 'plan_sha256': digest})
        return {'schema': 'nexus.operator.host-census.v1',
                'status': 'blocked-unfinished' if pending else 'clear',
                'journal_count': len(journals), 'finished_count': finished,
                'unfinished': pending, 'authority': 'none',
                'jobs_restarted': False, 'orphaned_processes_ruled_out': False,
                'production_attested': False}
    finally:
        os.close(dfd)


def docker_inventory(*, executable: str = 'docker') -> dict:
    """Read-only best-effort view of labelled NEXUS containers on one daemon.

    Absence of a label is NOT proof of no orphan: older executions, another
    daemon/context, stopped/removed containers and non-Docker PIDs are outside
    this observation. Never run rm, kill, inspect secrets, or start containers.
    """
    result = {'status': 'unverifiable', 'labelled_container_count': None,
              'container_ids': [], 'orphaned_processes_ruled_out': False,
              'production_attested': False, 'authority': 'none'}
    if not isinstance(executable, str) or not executable or '/' in executable:
        return result
    binary = shutil.which(executable)
    if not binary:
        return result
    try:
        cmd = [binary, 'ps', '--all', '--no-trunc',
               '--filter', 'label=nexus.operator.managed=1', '--format', '{{.ID}}']
        process = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,
                                 text=True, timeout=6, check=False,
                                 env={'PATH': '/usr/bin:/bin', 'DOCKER_CONFIG': '/nonexistent'})
    except (OSError, UnicodeError, ValueError, subprocess.TimeoutExpired):
        return result
    if process.returncode or len(process.stdout) > 20_000:
        return result
    ids = process.stdout.splitlines()
    if len(ids) > MAX_MANAGED_CONTAINERS or any(not _SHA256.fullmatch(x) for x in ids) or len(ids) != len(set(ids)):
        return result
    return {**result, 'status': 'labelled-containers-observed' if ids else 'no-labelled-containers-observed',
            'labelled_container_count': len(ids), 'container_ids': sorted(ids)}
