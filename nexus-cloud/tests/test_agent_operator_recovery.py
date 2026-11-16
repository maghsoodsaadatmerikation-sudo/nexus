"""Operator-only crash recovery: no replay, no live-socket revocation."""
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from agent_journal import ApprovalJournal
from agent_operator_service import (
    OperatorServer, TOKEN_NAME, SOCKET_NAME, LOCK_NAME, recover_stale_service,
)
from agent_workspace import Workspace, WorkspaceDenied

CLI = Path(__file__).resolve().parents[2] / 'scripts' / 'nexus-operator-service.py'


@pytest.fixture
def private(tmp_path):
    if os.getuid() == 0:
        pytest.skip('owner-only services require nonroot')
    root = tmp_path / 'private'
    root.mkdir(mode=0o700)
    return root


def test_live_service_cannot_be_revoked_or_started_twice(private):
    with OperatorServer(private) as server:
        with pytest.raises(WorkspaceDenied, match='service-still-active'):
            OperatorServer(private)
        with pytest.raises(WorkspaceDenied, match='service-still-active'):
            recover_stale_service(private, acknowledge_possible_orphans=True)
        assert (private / TOKEN_NAME).is_file()
        assert (private / SOCKET_NAME).is_socket()
        assert (private / LOCK_NAME).is_file()
    assert not (private / TOKEN_NAME).exists()
    assert not (private / SOCKET_NAME).exists()
    assert (private / LOCK_NAME).stat().st_mode & 0o077 == 0


def test_recover_crashed_daemon_preserves_started_approval(private):
    ws = Workspace(private, 'alpha')
    digest = hashlib.sha256(b'unrepeatable-approved-plan').hexdigest()
    with ws.operation_lock():
        ApprovalJournal(ws).claim(digest, version=4,
                                  workspace_before=ws.manifest()['sha256'],
                                  execution_nonce='a'*32)
    proc = subprocess.Popen([sys.executable, str(CLI), 'serve', '--root', str(private)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True)
    try:
        # Its readiness line is printed only after binding the private socket.
        line = proc.stdout.readline()
        assert json.loads(line)['status'] == 'operator-local-ready'
        assert (private / SOCKET_NAME).is_socket()
        os.kill(proc.pid, signal.SIGKILL)
        assert proc.wait(timeout=3) != 0
        with pytest.raises(WorkspaceDenied, match='acknowledgment'):
            recover_stale_service(private)
        assert (private / TOKEN_NAME).exists() and (private / SOCKET_NAME).exists()
        with pytest.raises((WorkspaceDenied, OSError)):
            OperatorServer(private)  # never auto-resume with an old token
        report = recover_stale_service(private, acknowledge_possible_orphans=True)
        assert report == {'status': 'stale-transport-revoked', 'authority': 'operator-only',
                          'journal_preserved': True, 'jobs_restarted': False,
                          'orphaned_processes_ruled_out': False}
        assert not (private / TOKEN_NAME).exists()
        assert not (private / SOCKET_NAME).exists()
        with ws.operation_lock():
            record = ApprovalJournal(ws).read(digest)
            assert record['state'] == 'started'
            with pytest.raises(WorkspaceDenied, match='approval-already-consumed'):
                ApprovalJournal(ws).claim(digest, version=4,
                                          workspace_before=record['workspace_sha256_before'],
                                          execution_nonce='a'*32)
        with OperatorServer(private) as server:
            assert (private / TOKEN_NAME).exists()
            assert (private / SOCKET_NAME).is_socket()
        assert recover_stale_service(private, acknowledge_possible_orphans=True)['status'] == 'no-stale-transport'
    finally:
        if proc.poll() is None:
            proc.kill(); proc.wait(timeout=3)
        proc.stdout.close(); proc.stderr.close()


def test_malformed_stale_token_is_not_deleted(private):
    with OperatorServer(private):
        pass
    (private / TOKEN_NAME).write_text('not-a-token')
    (private / TOKEN_NAME).chmod(0o600)
    with pytest.raises(WorkspaceDenied, match='credential'):
        recover_stale_service(private, acknowledge_possible_orphans=True)
    assert (private / TOKEN_NAME).exists()
    (private / TOKEN_NAME).unlink()
    (private / TOKEN_NAME).symlink_to(private / LOCK_NAME)
    with pytest.raises(WorkspaceDenied):
        recover_stale_service(private, acknowledge_possible_orphans=True)
    assert (private / TOKEN_NAME).is_symlink()


def test_server_shutdown_waits_for_workers_before_releasing_lock(private):
    server = OperatorServer(private)
    stopped = threading.Event()
    cancelled = threading.Event()
    def worker():
        if cancelled.wait(6):
            time.sleep(.15)  # simulate cleanup of an in-flight guest
        stopped.set()
    thread = threading.Thread(target=worker)
    server._running['alpha'] = ('a'*64, cancelled)
    server._worker_threads['alpha'] = thread
    thread.start()
    try:
        server.server_close()
        assert cancelled.is_set() and stopped.is_set() and not thread.is_alive()
        assert server._service_lock_fd == -1
        with OperatorServer(private):
            pass
    finally:
        if thread.is_alive():
            cancelled.set(); thread.join(3)


def test_old_unlocked_live_listener_cannot_be_revoked(private):
    # Compatibility with an older service lacking the lifetime flock: the
    # socket still has to prove it is not accepting connections.
    (private / TOKEN_NAME).write_text('a'*64)
    (private / TOKEN_NAME).chmod(0o600)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(private / SOCKET_NAME))
        os.chmod(private / SOCKET_NAME, 0o600)
        listener.listen(2)
        with pytest.raises(WorkspaceDenied, match='active-or-unverifiable'):
            recover_stale_service(private, acknowledge_possible_orphans=True)
        assert (private / SOCKET_NAME).is_socket()
        assert (private / TOKEN_NAME).exists()


def test_stale_recovery_command_requires_explicit_operator_flag(private):
    args = [sys.executable, str(CLI), 'recover-stale', '--root', str(private)]
    refusal = subprocess.run(args, capture_output=True, text=True, timeout=4)
    assert refusal.returncode == 2 and 'denied' in refusal.stderr
    allowed = subprocess.run([*args, '--acknowledge-possible-orphans'],
                             capture_output=True, text=True, timeout=4)
    assert allowed.returncode == 0 and json.loads(allowed.stdout)['status'] == 'no-stale-transport'
    for unwanted in ('token', 'digest', 'secret', 'private_plan', 'stdout'):
        assert unwanted not in allowed.stdout
