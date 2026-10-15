#!/usr/bin/env python3
"""Real-process launcher checks; only fresh synthetic state is used."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import select
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    script = Path(__file__).with_name('run-local-pilot.py')
    spec = importlib.util.spec_from_file_location('snapshot', script.with_name('data-snapshot.py'))
    snapshot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(snapshot)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with tempfile.TemporaryDirectory(prefix='nexus-launcher-test-') as tmp:
        root = Path(tmp)
        state = root / 'state'
        children = []
        gateway_handles = []

        def command(directory):
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                port = listener.getsockname()[1]
            return [sys.executable, str(script), '--binary', str(binary),
                    '--state-dir', str(directory), '--port', str(port)]

        def maintenance(directory, *arguments):
            return subprocess.run([sys.executable, str(script), '--state-dir', str(directory),
                *map(str, arguments)], capture_output=True, text=True, timeout=10)

        def start(directory, expected):
            process = subprocess.Popen(command(directory), stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True)
            children.append(process)
            assert select.select([process.stdout], [], [], 15)[0], 'launcher startup timeout'
            line = process.stdout.readline()
            assert line, 'launcher exited without startup confirmation'
            info = json.loads(line)
            assert info['state'] == expected and info['url'].startswith('http://127.0.0.1:')
            gateway_handles.append(os.pidfd_open(info['gateway_pid']))
            token = (directory / 'api-token').read_text().strip()
            assert token not in line
            assert stat.S_IMODE(directory.stat().st_mode) == 0o700
            assert stat.S_IMODE((directory / 'api-token').stat().st_mode) == 0o600
            return process, info['url'], token

        def stop(process, token):
            process.terminate()
            stdout, stderr = process.communicate(timeout=10)
            assert process.returncode == 0
            assert token not in stdout + stderr

        def call(base, token, method, body=None):
            request = urllib.request.Request(base + '/v1/requests', method=method,
                headers={'authorization': 'Bearer ' + token, 'content-type': 'application/json'},
                data=json.dumps(body).encode() if body is not None else None)
            try:
                response = opener.open(request, timeout=3)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                return response.status

        try:
            process, base, token = start(state, 'ready')
            body = {'request_id': 'launcher-test', 'authority': 'user', 'action': 'present',
                    'value': 'synthetic', 'payload': 'opaque'}
            assert call(base, token, 'POST', body) == 202
            archive = root / 'snapshot.json'
            blocked = maintenance(state, '--backup', archive, '--offline')
            assert blocked.returncode != 0 and 'already in use' in blocked.stderr
            assert not archive.exists()
            denied = subprocess.run(command(state), capture_output=True, text=True, timeout=5)
            assert denied.returncode != 0 and 'already in use' in denied.stderr
            stop(process, token)
            process, base, same_token = start(state, 'ready')
            assert same_token == token
            assert call(base, token, 'POST', body) == 409
            # SIGKILL cannot free a lock still inherited by a live child.
            process.kill()
            process.wait(timeout=5)
            denied = subprocess.run(command(state), capture_output=True, text=True, timeout=5)
            assert denied.returncode != 0 and 'already in use' in denied.stderr
            assert maintenance(state, '--backup', archive, '--offline').returncode != 0
            assert not archive.exists()
            signal.pidfd_send_signal(gateway_handles[-1], signal.SIGTERM)
            # Wait until the orphan is no longer holding the lock, bounded.
            import fcntl
            import time
            with (state / 'operator.lock').open('rb') as handle:
                deadline = time.monotonic() + 5
                while True:
                    try:
                        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        fcntl.flock(handle, fcntl.LOCK_UN)
                        break
                    except BlockingIOError:
                        assert time.monotonic() < deadline
                        time.sleep(.05)
            missing = root / 'missing'
            assert maintenance(missing, '--backup', archive, '--offline').returncode != 0
            assert not missing.exists() and not archive.exists()
            assert maintenance(state, '--backup', archive).returncode != 0
            assert not archive.exists()
            captured = maintenance(state, '--backup', archive, '--offline')
            assert captured.returncode == 0, captured.stderr
            saved = archive.read_bytes()
            assert token.encode() not in saved
            document = json.loads(saved)
            assert all(record['path'] not in ('api-token', 'operator.lock')
                       for record in document['files'])
            assert any(record['path'].startswith('requests/') for record in document['files'])
            assert maintenance(state, '--backup', archive, '--offline').returncode != 0
            assert archive.read_bytes() == saved
            restored = root / 'recovered'
            assert maintenance(restored, '--restore', archive).returncode != 0
            assert not restored.exists()
            recovered = maintenance(restored, '--restore', archive, '--offline')
            assert recovered.returncode == 0, recovered.stderr
            assert not (restored / 'api-token').exists()
            assert maintenance(restored, '--restore', archive, '--offline').returncode != 0
            assert (state / 'api-token').read_text().strip() == token
            process, base, restored_token = start(restored, 'recovery-quarantined')
            request = urllib.request.Request(base + '/v1/requests/launcher-test',
                headers={'authorization': 'Bearer ' + restored_token})
            with opener.open(request, timeout=3) as response:
                assert response.status == 200
                assert json.load(response) == {'request_id': 'launcher-test', 'status': 'pending'}
            assert call(base, restored_token, 'POST', body) == 503
            stop(process, restored_token)
            assert (restored / 'data' / snapshot.RECOVERY_MARKER).exists()
            # Insecure existing state and token symlinks must fail without replacement.
            insecure = root / 'insecure'
            insecure.mkdir(mode=0o755)
            insecure.chmod(0o755)
            rejected = subprocess.run(command(insecure), capture_output=True, text=True, timeout=5)
            assert rejected.returncode != 0 and not (insecure / 'api-token').exists()
            linked = root / 'linked'
            linked.mkdir(mode=0o700)
            sentinel = root / 'sentinel'
            sentinel.write_text('preserve')
            (linked / 'api-token').symlink_to(sentinel)
            rejected = subprocess.run(command(linked), capture_output=True, text=True, timeout=5)
            assert rejected.returncode != 0 and sentinel.read_text() == 'preserve'
        finally:
            for child in children:
                if child.poll() is None:
                    child.terminate()
                    child.communicate(timeout=10)
            for handle in gateway_handles:
                try:
                    signal.pidfd_send_signal(handle, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                finally:
                    os.close(handle)
    print(json.dumps({'status': 'PASS', 'scope': 'synthetic-local-launcher-only',
        'private_persistent_token': True, 'duplicate_launcher_rejected': True,
        'orphan_child_preserves_lock': True, 'restart_preserves_request': True,
        'quarantine_not_resumed': True, 'insecure_state_and_symlink_rejected': True,
        'maintenance_rejects_live_and_orphan_writers': True,
        'backup_excludes_credentials_and_keeps_request_ledger': True,
        'maintenance_requires_offline_and_refuses_overwrite': True,
        'production_data_recovered': False, 'authority': 'none'}, sort_keys=True))


if __name__ == '__main__':
    main()
