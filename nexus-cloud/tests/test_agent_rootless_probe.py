"""Operator-only rootless namespace probe: negative fixtures and OS acceptance."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest
from agent_rootless_probe import static_elf, private_executable, run_probe, validate_args
from agent_workspace import WorkspaceDenied

SOURCE = Path(__file__).resolve().parents[2] / 'scripts' / 'rootless-sandbox-probe.c'


def require_real_namespaces():
    """Only the dedicated OS job may claim a real namespace acceptance PASS.

    General-purpose CI/static jobs can run on kernels with unprivileged userns
    disabled. They must label the OS portion SKIPPED, never fabricate PASS.
    The separately configured rootless-namespace CI job requires this probe.
    """
    result = subprocess.run(['unshare', '--user', '--map-root-user', '--mount',
                             '--net', '--pid', '--fork', '/usr/bin/true'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            timeout=3, check=False)
    if result.returncode != 0:
        if os.environ.get('NEXUS_ROOTLESS_ACCEPTANCE') == 'required':
            pytest.fail('mandatory-rootless-OS-namespace-unavailable')
        pytest.skip('real-rootless-OS-namespace-unavailable; separate mandatory CI job is authoritative')


def build_binary(tmp_path):
    if not shutil.which('cc'):
        pytest.fail('rootless acceptance requires static C compiler')
    out = tmp_path / 'bin'
    out.mkdir(mode=0o700)
    exe = out / 'nexus-operator-probe'
    p = subprocess.run(['cc', '-static', '-Os', str(SOURCE), '-o', str(exe)],
                       capture_output=True, text=True, timeout=35)
    assert p.returncode == 0, p.stderr[-500:]
    exe.chmod(0o500)
    return exe, hashlib.sha256(exe.read_bytes()).hexdigest()


def fixture(tmp_path):
    root = tmp_path / 'operator-private'
    root.mkdir(mode=0o700)
    project = root / 'alpha'
    project.mkdir(mode=0o700)
    (project / 'input.txt').write_text('sentinel')
    (project / 'input.txt').chmod(0o600)
    return root, project


def test_static_elf_rejects_scripts_and_interpreted_binaries(tmp_path):
    assert not static_elf(b'#!/bin/sh\n')
    assert not static_elf(b'\x7fELF' + b'\x00' * 150)
    if Path('/usr/bin/python3').exists():
        assert not static_elf(Path('/usr/bin/python3').read_bytes())
    exe, digest = build_binary(tmp_path)
    assert static_elf(exe.read_bytes())
    assert private_executable(exe, digest) == exe.read_bytes()
    with pytest.raises(WorkspaceDenied, match='digest-mismatch'):
        private_executable(exe, '0' * 64)


def test_plan_provenance_requires_exact_reviewed_static_elf(tmp_path):
    exe, digest = build_binary(tmp_path)
    exe.chmod(0o755)
    with pytest.raises(WorkspaceDenied, match='not-private'):
        private_executable(exe, digest)
    exe.chmod(0o500)
    alias = exe.parent / 'alias'
    alias.symlink_to(exe)
    with pytest.raises(WorkspaceDenied):
        private_executable(alias, digest)
    alias.unlink()
    os.link(exe,alias)
    with pytest.raises(WorkspaceDenied, match='not-private'):
        private_executable(exe, digest)
    alias.unlink()
    exe.parent.chmod(0o755)
    with pytest.raises(WorkspaceDenied, match='parent-not-private'):
        private_executable(exe, digest)


def test_executable_rejects_ancestor_symlink_and_writable_parent(tmp_path):
    exe, digest = build_binary(tmp_path)
    alias = tmp_path / 'linked-directory'
    alias.symlink_to(exe.parent, target_is_directory=True)
    with pytest.raises((OSError, WorkspaceDenied)):
        private_executable(alias / exe.name, digest)
    alias.unlink()
    # The immediate directory remains private, but its ancestor becomes
    # group/world writable and can be replaced by another local account.
    exe.parent.parent.chmod(0o777)
    with pytest.raises(WorkspaceDenied, match='writable-ancestor'):
        private_executable(exe, digest)
    exe.parent.parent.chmod(0o700)
    assert private_executable(exe, digest) == exe.read_bytes()


def test_argv_timeout_and_approval_boundary(tmp_path):
    for arguments in [["\x00"], ['x'] * 17, ['é' * 2200], 'unsafe']:
        with pytest.raises(WorkspaceDenied):
            validate_args(arguments, 5)
    for t in [0, -1, 16, 1.5, True]:
        with pytest.raises(WorkspaceDenied):
            validate_args([], t)
    root, _ = fixture(tmp_path)
    exe, digest = build_binary(tmp_path)
    with pytest.raises(WorkspaceDenied, match='operator-approval'):
        run_probe(root, 'alpha', exe, digest)


@pytest.mark.skipif(os.getuid() == 0, reason='rootless must execute as nonroot')
def test_actual_unprivileged_namespace_limits_and_no_network(tmp_path):
    require_real_namespaces()
    root, project = fixture(tmp_path)
    exe, digest = build_binary(tmp_path)
    before = sorted(p.name for p in project.iterdir())
    receipt = run_probe(root, 'alpha', exe, digest, approved=True, timeout=12)
    assert receipt['schema'] == 'nexus.rootless-probe.v1'
    assert receipt['status'] == 'complete' and receipt['exit_code'] == 0, receipt
    assert receipt['stdout_sha256'] == hashlib.sha256(b'NEXUS_ROOTLESS_PROBE_PASS\n').hexdigest()
    assert receipt['stderr_bytes'] == 0
    # The trusted C fixture also asserts zero effective/permitted/inheritable
    # capabilities, no-new-privileges, and denial of guest remount attempts.
    assert not receipt['tenant_execution_enabled'] and not receipt['production_isolation_attested']
    assert sorted(p.name for p in project.iterdir()) == before
    assert not (project / 'pwned.txt').exists()
    assert not any(p.name.startswith('.nexus-rootless-') for p in root.iterdir())


@pytest.mark.skipif(os.getuid() == 0, reason='rootless must execute as nonroot')
def test_source_mutation_or_workspace_links_block_before_execution(tmp_path):
    root, project = fixture(tmp_path)
    exe, digest = build_binary(tmp_path)
    with pytest.raises(WorkspaceDenied, match='digest-mismatch'):
        run_probe(root, 'alpha', exe, '0'*64, approved=True)
    (project/'escape').symlink_to('/etc')
    with pytest.raises(WorkspaceDenied, match='manifest-rejects-links'):
        run_probe(root, 'alpha', exe, digest, approved=True)
    assert not (project/'pwned.txt').exists()


@pytest.mark.skipif(os.getuid() == 0, reason='rootless must execute as nonroot')
def test_no_unbounded_output_or_unbounded_lifetime(tmp_path):
    require_real_namespaces()
    root, project = fixture(tmp_path)
    exe, digest = build_binary(tmp_path)
    spam = run_probe(root, 'alpha', exe, digest, args=['--spam'], approved=True, timeout=10)
    assert spam['status'] == 'output-limit' and spam['stdout_bytes'] <= 65_536
    slow = run_probe(root, 'alpha', exe, digest, args=['--sleep'], approved=True, timeout=2)
    assert slow['status'] == 'timeout' and slow['exit_code'] != 0
    assert not (project / 'pwned.txt').exists()


def test_parent_guard_refuses_wrong_parent_pid_and_remains_unprivileged():
    from agent_rootless_probe import _guarded_command
    cmd = _guarded_command('/usr/bin/true', [], parent_pid=os.getpid() + 100000)
    result = subprocess.run(cmd, capture_output=True, timeout=4)
    assert result.returncode == 120
    assert result.stdout == b'' and result.stderr == b''
    good = subprocess.run(_guarded_command('/usr/bin/true', []),
                          capture_output=True, timeout=4)
    assert good.returncode == 0
    with pytest.raises(WorkspaceDenied):
        _guarded_command('bin/unshare', [])


def test_parent_guard_terminates_guest_on_abrupt_operator_death(tmp_path):
    """Real SIGKILL of operator process; no mock parent or guest lifecycle."""
    from agent_rootless_probe import _guarded_command
    start = tmp_path / 'started'; done = tmp_path / 'done'
    guest = tmp_path / 'guest.py'
    guest.write_text('import pathlib,sys,time\npathlib.Path(sys.argv[1]).write_text("started")\ntime.sleep(2.5)\npathlib.Path(sys.argv[2]).write_text("done")\n')
    owner = tmp_path / 'owner.py'
    owner.write_text('import os,subprocess,sys\nfrom agent_rootless_probe import _guarded_command\n'
                     'p=subprocess.Popen(_guarded_command(sys.executable, ["-I", sys.argv[1],sys.argv[2],sys.argv[3]]), '
                     'stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=True)\n'
                     'print(p.pid,flush=True)\np.wait()\n')
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1])}
    owner_proc = subprocess.Popen([sys.executable, str(owner), str(guest),str(start),str(done)],
                                  stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                  text=True, env=env)
    try:
        child_pid = int(owner_proc.stdout.readline().strip())
        limit = time.monotonic() + 4
        while not start.exists() and time.monotonic() < limit:
            time.sleep(.02)
        assert start.exists(), 'guarded child never started'
        os.kill(owner_proc.pid, 9)
        owner_proc.wait(timeout=4)
        time.sleep(2.9)
        assert not done.exists(), 'orphaned guest survived operator SIGKILL'
    finally:
        if owner_proc.poll() is None:
            owner_proc.kill(); owner_proc.wait(timeout=3)
        owner_proc.stdout.close();owner_proc.stderr.close()
