"""Phase 14: operator-only, read-only rootless Linux namespace proof.

This is NOT a tenant execution backend or an agent tool. A separately
approved, SHA-256-pinned static ELF probe runs with a private user/mount/PID/
network/IPC/UTS namespace, no host root, no Docker and no host filesystem
except a read-only workspace. Failure to establish every boundary is fatal.
"""
from __future__ import annotations

import ctypes
import hashlib
import os
from pathlib import Path
import re
import resource
import selectors
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent_workspace import Workspace, WorkspaceDenied

MAX_EXEC_BYTES = 8 * 1024 * 1024
MAX_OUTPUT_BYTES = 65_536
MAX_ARGS_BYTES = 4_096
DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def static_elf(data: bytes) -> bool:
    """Reject scripts, dynamic-interpreter ELFs, unsupported architectures."""
    if len(data) < 64 or data[:4] != b'\x7fELF' or data[4:6] != b'\x02\x01':
        return False
    etype, machine = struct.unpack_from('<HH', data, 16)
    phoff = struct.unpack_from('<Q', data, 32)[0]
    entsize, count = struct.unpack_from('<HH', data, 54)
    if etype not in (2, 3) or machine not in (62, 183) or entsize != 56 or not 1 <= count <= 128:
        return False
    if phoff < 64 or phoff + entsize * count > len(data):
        return False
    return all(struct.unpack_from('<I', data, phoff + i * entsize)[0] != 3 for i in range(count))


def private_executable(path: str | Path, digest: str) -> bytes:
    if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
        raise WorkspaceDenied('rootless-executable-digest-required')
    p = Path(path)
    if not p.is_absolute() or '..' in p.parts or p.is_symlink():
        raise WorkspaceDenied('rootless-executable-path')
    parent = p.parent.stat()
    if (p.parent.is_symlink() or not stat.S_ISDIR(parent.st_mode) or
            parent.st_uid != os.getuid() or parent.st_mode & 0o077):
        raise WorkspaceDenied('rootless-executable-parent-not-private')
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    fd = os.open(p, flags)
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or
                st.st_mode & 0o077 or st.st_nlink != 1 or not 64 <= st.st_size <= MAX_EXEC_BYTES):
            raise WorkspaceDenied('rootless-executable-not-private')
        data = os.read(fd, MAX_EXEC_BYTES + 1)
        if len(data) != st.st_size or len(data) > MAX_EXEC_BYTES or not static_elf(data):
            raise WorkspaceDenied('rootless-executable-not-static-elf')
        if hashlib.sha256(data).hexdigest() != digest:
            raise WorkspaceDenied('rootless-executable-digest-mismatch')
        return data
    finally:
        os.close(fd)


def validate_args(argv: list[str], timeout: int) -> None:
    if (not isinstance(argv, list) or len(argv) > 16 or
            any(not isinstance(x, str) or '\x00' in x or len(x) > 1024 for x in argv) or
            sum(len(x.encode('utf-8')) for x in argv) > MAX_ARGS_BYTES):
        raise WorkspaceDenied('rootless-argv-boundary')
    if type(timeout) is not int or not 1 <= timeout <= 15:
        raise WorkspaceDenied('rootless-time-limit')


def _mount(*args: str) -> None:
    p = subprocess.run(['/usr/bin/mount', *args], stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       close_fds=True, timeout=4, check=False,
                       env={'PATH': '/usr/bin:/bin'})
    if p.returncode != 0:
        raise WorkspaceDenied('rootless-mount-failed')


def _enter(root: str, workspace: str, args: list[str]) -> None:
    """Trusted bootstrap, executed only after unshare installed all namespaces."""
    import socket
    # This runs as uid 0 *inside a new user namespace*, mapped to the calling
    # unprivileged host UID, not as privileged host root.
    if os.getuid() != 0 or os.getpid() != 1:
        raise WorkspaceDenied('rootless-not-remapped-user')
    net = os.readlink('/proc/self/ns/net')
    # The caller compares namespace identity to its own parent. This check
    # protects the obvious case where a wrapper simply omitted --net.
    if not net.startswith('net:['):
        raise WorkspaceDenied('rootless-network-namespace-unavailable')
    for k, limit in ((resource.RLIMIT_FSIZE, 4 * 1024 * 1024),
                     (resource.RLIMIT_NOFILE, 64), (resource.RLIMIT_CORE, 0),
                     (resource.RLIMIT_NPROC, 64), (resource.RLIMIT_CPU, 7)):
        soft, hard = resource.getrlimit(k)
        value = min(limit, hard) if hard != resource.RLIM_INFINITY else limit
        resource.setrlimit(k, (value, value))
    # A host-private staging directory becomes read-only *inside this new
    # mount namespace*. No host /bin, /lib, /etc, /home, or /proc is exposed.
    _mount('--bind', root, root)
    _mount('-o', 'remount,bind,ro', root)
    _mount('--bind', workspace, root + '/workspace')
    _mount('-o', 'remount,bind,ro', root + '/workspace')
    _mount('-t', 'tmpfs', '-o', 'size=16m,nosuid,nodev,noexec,mode=700',
           'tmpfs', root + '/tmp')
    if not os.statvfs(root).f_flag & os.ST_RDONLY:
        raise WorkspaceDenied('rootless-root-not-readonly')
    if not os.statvfs(root + '/workspace').f_flag & os.ST_RDONLY:
        raise WorkspaceDenied('rootless-workspace-not-readonly')
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
    # NoNewPrivs before any untrusted executable. No setuid/setgid files are
    # mounted; capabilities in the nested namespace do not apply on the host.
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) != 0:
        raise WorkspaceDenied('rootless-nnp-failed')
    os.chroot(root)
    os.chdir('/workspace')
    os.execve('/bin/probe', ['/bin/probe', *args],
              {'PATH': '/bin', 'HOME': '/tmp', 'LANG': 'C', 'TMPDIR': '/tmp'})


def _pump(proc: subprocess.Popen, timeout: int) -> tuple[str, int, bytes, bytes]:
    out, err = bytearray(), bytearray()
    deadline = time.monotonic() + timeout
    reason = 'complete'
    with selectors.DefaultSelector() as select:
        for stream, buf in ((proc.stdout, out), (proc.stderr, err)):
            os.set_blocking(stream.fileno(), False)
            select.register(stream, selectors.EVENT_READ, buf)
        while select.get_map() or proc.poll() is None:
            if time.monotonic() >= deadline:
                reason = 'timeout'
                break
            for key, _ in select.select(min(.10, max(0, deadline - time.monotonic()))):
                chunk = os.read(key.fileobj.fileno(), 16_384)
                if not chunk:
                    select.unregister(key.fileobj)
                else:
                    key.data.extend(chunk)
                    if len(out) + len(err) > MAX_OUTPUT_BYTES:
                        reason = 'output-limit'
                        break
            if reason != 'complete':
                break
    if reason != 'complete':
        import signal
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        code = proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill(); code = proc.wait(timeout=2)
        reason = 'timeout'
    return reason, code, bytes(out[:MAX_OUTPUT_BYTES]), bytes(err[:MAX_OUTPUT_BYTES])


def run_probe(root: str | Path, workspace: str, executable: str | Path,
              expected_sha256: str, *, args: list[str] | None = None,
              timeout: int = 6, approved: bool = False) -> dict:
    """Operator action only. No agent-plan execution or browser export."""
    if approved is not True or os.name != 'posix' or not sys.platform.startswith('linux') or os.getuid() == 0:
        raise WorkspaceDenied('rootless-needs-separate-unprivileged-operator-approval')
    args = [] if args is None else args
    validate_args(args, timeout)
    blob = private_executable(executable, expected_sha256)
    if not Path('/usr/bin/unshare').is_file() or not Path('/usr/bin/mount').is_file():
        raise WorkspaceDenied('rootless-linux-tools-unavailable')
    ws = Workspace(root, workspace)
    started = time.monotonic()
    with ws.operation_lock():
        observed = ws.manifest()['sha256']  # refuse symlinks / hardlinks / devices
        with tempfile.TemporaryDirectory(prefix='.nexus-rootless-', dir=ws.root) as stage:
            top = Path(stage)
            sandbox = top / 'rootfs'
            (sandbox / 'bin').mkdir(parents=True, mode=0o700)
            (sandbox / 'workspace').mkdir(mode=0o700)
            (sandbox / 'tmp').mkdir(mode=0o700)
            program = sandbox / 'bin' / 'probe'
            with program.open('xb') as stream:
                stream.write(blob); stream.flush(); os.fsync(stream.fileno())
            program.chmod(0o500)
            cmd = ['/usr/bin/unshare', '--user', '--map-root-user', '--mount',
                   '--net', '--pid', '--ipc', '--uts', '--fork', '--kill-child',
                   '--propagation', 'private', sys.executable, '-I', __file__,
                   '__enter__', str(sandbox), str(ws.path), *args]
            proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    close_fds=True, start_new_session=True,
                                    env={'PATH': '/usr/bin:/bin', 'LANG': 'C'})
            status, code, out, err = _pump(proc, timeout)
    # The caller gets proof metadata only, not arbitrary untrusted stdout.
    # Any bootstrap failure is fail-closed, never an isolation success.
    if status == 'complete' and code != 0:
        status = 'sandbox-failed'
    return {'schema': 'nexus.rootless-probe.v1', 'status': status,
            'exit_code': code, 'stdout_sha256': hashlib.sha256(out).hexdigest(),
            'stderr_sha256': hashlib.sha256(err).hexdigest(),
            'stdout_bytes': len(out), 'stderr_bytes': len(err),
            'source_sha256': expected_sha256,
            'workspace_sha256_at_start': observed,
            'duration_ms': int((time.monotonic() - started) * 1000),
            'namespace_policy': 'user+mount+net+pid+ipc+uts;ro-workspace;tmpfs-only',
            'tenant_execution_enabled': False,
            'production_isolation_attested': False, 'authority': 'operator-only'}


if __name__ == '__main__' and len(sys.argv) >= 4 and sys.argv[1] == '__enter__':
    try:
        _enter(sys.argv[2], sys.argv[3], sys.argv[4:])
    except BaseException:
        # Do not write private file content or exception messages to stderr.
        os._exit(120)
