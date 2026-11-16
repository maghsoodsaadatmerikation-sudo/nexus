"""Read-only Linux admission checks for distinct NEXUS operator OS identities.

This module NEVER creates OS users, moves processes into cgroups, starts an
agent or gives a model capabilities. A PASS requires existing host separation;
it cannot certify containers, kernels, Docker daemon or hostile-root safety.
"""
from __future__ import annotations

import os
import re
import socket
import stat
from dataclasses import dataclass
from pathlib import Path

from agent_workspace import WorkspaceDenied
from agent_operator_service import SOCKET_NAME, TOKEN_NAME

MAX_TENANTS = 32
MAX_MEMORY = 512 * 1024 * 1024  # per service cgroup, not Docker daemon
MAX_PIDS = 128
MAX_CPU_MILLI = 2000  # <= 2 host CPUs
_CGROUP_ROOT = Path('/sys/fs/cgroup')


def _deny(reason: str):
    raise WorkspaceDenied('tenant-' + reason)


def _private_root(root: Path, uid: int) -> None:
    """Walk each ancestor with O_NOFOLLOW; never trust a string prefix."""
    if not root.is_absolute() or '..' in root.parts or root == Path('/'):
        _deny('root-path')
    flags = os.O_DIRECTORY | os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open('/', flags)
    try:
        for component in root.parts[1:]:
            nextfd = os.open(component, flags, dir_fd=fd)
            os.close(fd)
            fd = nextfd
            parent_st = os.fstat(fd)
            # A writable ancestor may permit pathname replacement between
            # preflight and later use. /tmp-style root-owned sticky dirs are
            # allowed; an attacker-owned sticky parent is not.
            if parent_st.st_mode & 0o022 and not (
                parent_st.st_mode & stat.S_ISVTX and parent_st.st_uid == 0
            ):
                _deny('writable-ancestor')
        st = os.fstat(fd)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != uid or st.st_mode & 0o077:
            _deny('root-mode-or-owner')
    finally:
        os.close(fd)


def _private_file(root: Path, name: str, uid: int, *, socket_file: bool) -> None:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    rootfd = os.open(root, flags)
    try:
        st = os.stat(name, dir_fd=rootfd, follow_symlinks=False)
        if (st.st_uid != uid or st.st_mode & 0o077 or
                (not stat.S_ISSOCK(st.st_mode) if socket_file else
                 not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_size != 64)):
            _deny('service-file-mode-or-owner')
    finally:
        os.close(rootfd)


def _pid_owns_listening_socket(pid: int, path: Path) -> bool:
    """Bind observed public socket pathname to an FD held by inspected PID."""
    if not hasattr(socket, 'AF_UNIX'):
        return False
    candidates = set()
    for line in Path('/proc/net/unix').read_text().splitlines()[1:]:
        parts = line.split(maxsplit=7)
        if len(parts) != 8 or parts[7] != str(path):
            continue
        try:
            if int(parts[3], 16) & 0x10000 and int(parts[4], 16) == 1:
                candidates.add(parts[6])
        except ValueError:
            return False
    if not candidates:
        return False
    try:
        handles = list((Path('/proc') / str(pid) / 'fd').iterdir())
    except OSError:
        return False
    for fd in handles:
        try:
            target = os.readlink(fd)
        except OSError:
            continue
        if target.startswith('socket:[') and target.endswith(']') and target[8:-1] in candidates:
            return True
    return False


def read_proc_status(text: str) -> tuple[int, int]:
    """Return fully matched real/effective/saved/filesystem UID and GID."""
    values = {}
    for line in text.splitlines():
        for key in ('Uid', 'Gid', 'Groups', 'NoNewPrivs', 'CapEff'):
            if line.startswith(key + ':'):
                if key in values:
                    _deny('duplicate-process-status')
                values[key] = line.split(':', 1)[1].strip()
    if set(values) != {'Uid', 'Gid', 'Groups', 'NoNewPrivs', 'CapEff'}:
        _deny('incomplete-process-status')
    try:
        ids = [int(x) for x in values['Uid'].split()]
        groups = [int(x) for x in values['Gid'].split()]
        supplementary = [int(x) for x in values['Groups'].split()]
        capabilities = int(values['CapEff'], 16)
    except ValueError:
        _deny('process-status-format')
    if (len(ids) != 4 or len(groups) != 4 or len(set(ids)) != 1 or
            len(set(groups)) != 1 or ids[0] <= 0 or groups[0] <= 0 or
            values['NoNewPrivs'] != '1' or capabilities != 0):
        _deny('privileged-or-mixed-identity')
    require_dedicated_groups(groups[0], supplementary)
    return ids[0], groups[0]


def quota_values(memory_text: str, pids_text: str, cpu_text: str) -> dict:
    """Finite cgroup v2 CPU, memory, PID boundaries; fail closed on 'max'."""
    try:
        if not memory_text.strip().isdecimal() or not pids_text.strip().isdecimal():
            _deny('unbounded-quota')
        memory, pids = int(memory_text), int(pids_text)
        values = cpu_text.strip().split()
        if len(values) != 2 or any(not a.isdecimal() for a in values):
            _deny('unbounded-cpu')
        quota, period = map(int, values)
    except ValueError:
        _deny('invalid-quota')
    if (not 64 * 1024 * 1024 <= memory <= MAX_MEMORY or not 8 <= pids <= MAX_PIDS or
            not 1000 <= period <= 1_000_000 or not 1 <= quota <= period * 2):
        _deny('quota-outside-policy')
    return {'memory_bytes': memory, 'pids_max': pids,
            'cpu_milli': (quota * 1000) // period}


def cgroup_location(text: str) -> str:
    lines = text.strip().splitlines()
    if len(lines) != 1 or not lines[0].startswith('0::/'):
        _deny('not-unified-cgroup-v2')
    path = lines[0][3:]
    if (path == '/' or not path.startswith('/') or '..' in path.split('/') or
            any(not re.fullmatch(r'[A-Za-z0-9_.@-]{1,96}', c) for c in path.split('/')[1:])):
        _deny('cgroup-path')
    return path


@dataclass(frozen=True)
class TenantEvidence:
    uid: int
    gid: int
    root: Path
    cgroup: str
    memory_bytes: int
    pids_max: int
    cpu_milli: int


def inspect_tenant(root: str | Path, pid: int, *, cgroup_base: Path = _CGROUP_ROOT,
                   proc_base: Path = Path('/proc')) -> TenantEvidence:
    """Read-only host inspection; callers cannot supply alternate paths in CLI."""
    if type(pid) is not int or not 1 <= pid <= 2_147_483_647:
        _deny('pid')
    status = (proc_base / str(pid) / 'status').read_text()
    uid, gid = read_proc_status(status)
    path = Path(root)
    _private_root(path, uid)
    _private_file(path, TOKEN_NAME, uid, socket_file=False)
    _private_file(path, SOCKET_NAME, uid, socket_file=True)
    if proc_base == Path('/proc') and not _pid_owns_listening_socket(pid, path / SOCKET_NAME):
        _deny('service-pid-not-socket-owner')
    group = cgroup_location((proc_base / str(pid) / 'cgroup').read_text())
    if group.rsplit('/', 1)[-1] not in (f'nexus-tenant-{uid}', f'nexus-tenant-{uid}.scope'):
        _deny('cgroup-not-dedicated-to-uid')
    # Real audit always uses /sys/fs/cgroup. Dependency injection exists only
    # for unit fixtures, not the user-facing host audit CLI.
    folder = cgroup_base.joinpath(*group.lstrip('/').split('/'))
    limits = quota_values((folder / 'memory.max').read_text(),
                          (folder / 'pids.max').read_text(),
                          (folder / 'cpu.max').read_text())
    return TenantEvidence(uid, gid, path, group, **limits)


def audit_tenants(tenants: list[tuple[str | Path, int]], *, cgroup_base: Path = _CGROUP_ROOT,
                  proc_base: Path = Path('/proc')) -> dict:
    if (not isinstance(tenants, list) or
            not 2 <= len(tenants) <= MAX_TENANTS):
        _deny('tenant-count')
    seen_uid, seen_gid, seen_root, seen_group = set(), set(), set(), set()
    reports = []
    for root, pid in tenants:
        proof = inspect_tenant(root, pid, cgroup_base=cgroup_base, proc_base=proc_base)
        rootstr = str(proof.root)
        if (proof.uid in seen_uid or proof.gid in seen_gid or
                rootstr in seen_root or proof.cgroup in seen_group):
            _deny('shared-identity-or-resources')
        # Tenant roots / cgroups may never nest, even when their owner differs.
        for existing in seen_root:
            if rootstr.startswith(existing + '/') or existing.startswith(rootstr + '/'):
                _deny('nested-roots')
        for existing in seen_group:
            if proof.cgroup.startswith(existing + '/') or existing.startswith(proof.cgroup + '/'):
                _deny('nested-cgroups')
        seen_uid.add(proof.uid); seen_gid.add(proof.gid)
        seen_root.add(rootstr); seen_group.add(proof.cgroup)
        reports.append({'uid': proof.uid, 'gid': proof.gid,
                        'memory_bytes': proof.memory_bytes,
                        'pids_max': proof.pids_max, 'cpu_milli': proof.cpu_milli})
    return {'schema': 'nexus.tenant-boundary.audit.v1', 'status': 'PASS',
            'isolation': 'host-uid-and-service-cgroup-only',
            'tenant_count': len(reports), 'tenants': reports,
            'production_attested': False, 'docker_isolation_attested': False,
            'authority': 'none'}



def require_dedicated_groups(primary_gid: int, supplementary_groups: list[int]) -> None:
    """Forbid ambient docker/host-operator groups, not just root group.

    Linux group 0 is not the only dangerous supplementary group: membership
    in docker, disk, lxd or an operator service group could defeat the UID
    boundary. Tenant operators must have their own dedicated primary GID and
    no additional supplementary GID. The primary GID may appear in getgroups().
    """
    if (type(primary_gid) is not int or primary_gid <= 0 or
            not isinstance(supplementary_groups, (list, tuple)) or
            any(type(g) is not int or g != primary_gid
                for g in supplementary_groups)):
        _deny('supplementary-groups-not-dedicated')


def harden_tenant_daemon(root: str | Path) -> dict:
    """Enforce host quotas and Linux NNP *before* creating a service socket.

    A NEXUS multi-tenant service MUST run as an already-provisioned dedicated
    unprivileged UID inside a bounded per-user cgroup v2. This function does
    not provision users, cgroups, namespaces, or Docker isolation.
    """
    import ctypes
    import resource

    if os.name != 'posix' or not hasattr(os, 'getresuid'):
        _deny('requires-linux')
    uids, gids = os.getresuid(), os.getresgid()
    if (0 in uids or 0 in gids or len(set(uids)) != 1 or len(set(gids)) != 1):
        _deny('daemon-not-dedicated-unprivileged-user')
    require_dedicated_groups(gids[0], os.getgroups())
    _private_root(Path(root), os.getuid())
    group = cgroup_location(Path('/proc/self/cgroup').read_text())
    if group.rsplit('/', 1)[-1] not in (f'nexus-tenant-{os.getuid()}', f'nexus-tenant-{os.getuid()}.scope'):
        _deny('cgroup-not-dedicated-to-uid')
    folder = _CGROUP_ROOT.joinpath(*group.lstrip('/').split('/'))
    limits = quota_values((folder / 'memory.max').read_text(),
                          (folder / 'pids.max').read_text(),
                          (folder / 'cpu.max').read_text())
    # Lower existing soft/hard limits, never raise a host limit.
    for kind, maximum in ((resource.RLIMIT_NOFILE, 256),
                          (resource.RLIMIT_FSIZE, 32 * 1024 * 1024),
                          (resource.RLIMIT_CORE, 0)):
        low, high = resource.getrlimit(kind)
        chosen = min(high, maximum) if high != resource.RLIM_INFINITY else maximum
        resource.setrlimit(kind, (min(low, chosen) if low != resource.RLIM_INFINITY
                                  else chosen, chosen))
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
        _deny('no-new-privileges-unavailable')
    uid, gid = read_proc_status(Path('/proc/self/status').read_text())
    if uid != os.getuid() or gid != os.getgid():
        _deny('privilege-proof-mismatch')
    os.umask(0o077)
    return {'status': 'host-preflight-passed', 'authority': 'operator-only',
            'isolation': 'dedicated-uid-bounded-service-cgroup', **limits}
