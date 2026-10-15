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
        gateway_pids = []

        def command(directory):
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                port = listener.getsockname()[1]
            return [sys.executable, str(script), '--binary', str(binary),
                    '--state-dir', str(directory), '--port', str(port)]

        def start(directory, expected):
            process = subprocess.Popen(command(directory), stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True)
            children.append(process)
            assert select.select([process.stdout], [], [], 15)[0], 'launcher startup timeout'
            line = process.stdout.readline()
            assert line, 'launcher exited without startup confirmation'
            info = json.loads(line)
            assert info['state'] == expected and info['url'].startswith('http://127.0.0.1:')
            gateway_pids.append(info['gateway_pid'])
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
            os.kill(gateway_pids[-1], signal.SIGTERM)
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
            archive = root / 'snapshot.json'
            snapshot.backup(state / 'data', archive)
            restored = root / 'recovered'
            restored.mkdir(mode=0o700)
            snapshot.restore(archive, restored / 'data')
            process, base, restored_token = start(restored, 'recovery-quarantined')
            assert call(base, restored_token, 'POST', body) == 503
            stop(process, restored_token)
            assert (restored / 'data' / snapshot.RECOVERY_MARKER).exists()
            # Insecure existing state and token symlinks must fail without replacement.
            insecure = root / 'insecure'
            insecure.mkdir(mode=0o755)
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
            for pid in gateway_pids:
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
    print(json.dumps({'status': 'PASS', 'scope': 'synthetic-local-launcher-only',
        'private_persistent_token': True, 'duplicate_launcher_rejected': True,
        'orphan_child_preserves_lock': True, 'restart_preserves_request': True,
        'quarantine_not_resumed': True, 'insecure_state_and_symlink_rejected': True,
        'production_data_recovered': False, 'authority': 'none'}, sort_keys=True))


if __name__ == '__main__':
    main()
