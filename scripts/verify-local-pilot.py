#!/usr/bin/env python3
"""Exercise an actual executable on loopback with disposable synthetic data only."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    spec = importlib.util.spec_from_file_location('snapshot', Path(__file__).with_name('data-snapshot.py'))
    snapshot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(snapshot)
    token = secrets.token_hex(32)
    # Ignore proxy environment variables for this strictly local witness.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with tempfile.TemporaryDirectory(prefix='nexus-local-pilot-') as temporary:
        root = Path(temporary)
        source = root / 'source'
        source.mkdir(mode=0o700)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        base = 'http://127.0.0.1:' + str(port)
        process = None

        def call(method, path, body=None, auth=True):
            headers = {'content-type': 'application/json'}
            if auth:
                headers['authorization'] = 'Bearer ' + token
            request = urllib.request.Request(base + path, method=method, headers=headers,
                data=json.dumps(body).encode() if body is not None else None)
            try:
                response = opener.open(request, timeout=3)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                if path == '/v1/requests' or path.startswith('/v1/requests/') or path == '/v1/workspaces' or path.startswith('/v1/workspaces/'):
                    assert response.headers.get('cache-control') == 'no-store', 'private API cache policy missing'
                raw = response.read(1024 * 1024)
                return response.status, json.loads(raw) if raw and response.status != 401 else None

        def stop():
            nonlocal process
            if process is not None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                process = None

        def start(data, expected_ready):
            nonlocal process
            env = dict(os.environ, NEXUS_API_TOKEN=token, NEXUS_DATA_DIR=str(data),
                       NEXUS_BIND_ADDR='127.0.0.1:' + str(port))
            process = subprocess.Popen([str(binary)], env=env, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError('gateway exited before readiness')
                try:
                    if call('GET', '/livez', auth=False)[0] == 200:
                        assert call('GET', '/readyz', auth=False)[0] == expected_ready
                        return
                except OSError:
                    pass
                time.sleep(.05)
            raise RuntimeError('gateway startup timed out')

        body = {'request_id': 'local-pilot-request', 'authority': 'user',
                'action': 'present', 'value': 'synthetic-local-pilot', 'payload': 'opaque'}
        pending = {'request_id': body['request_id'], 'status': 'pending'}
        try:
            start(source, 200)
            assert call('POST', '/v1/workspaces', {}, auth=False)[0] == 401
            code, workspace = call('POST', '/v1/workspaces', {
                'workspace_id': 'local-pilot', 'question': 'Synthetic recovery witness',
                'provenance_id': 'test:local-pilot'})
            assert code == 201 and workspace['workspace']['judgment'] is None
            assert call('POST', '/v1/requests', body) == (202, pending)
            assert call('GET', '/v1/requests/local-pilot-request') == (200, pending)
            stop()
            start(source, 200)
            assert call('GET', '/v1/workspaces/local-pilot') == (200, workspace)
            assert call('GET', '/v1/requests/local-pilot-request') == (200, pending)
            assert call('POST', '/v1/requests', body)[0] == 409
            stop()
            archive = root / 'offline-snapshot.json'
            snapshot.backup(source, archive)
            restored = root / 'restored'
            snapshot.restore(archive, restored)
            start(restored, 503)
            assert call('GET', '/v1/workspaces/local-pilot') == (200, workspace)
            assert call('GET', '/v1/requests/local-pilot-request') == (200, pending)
            assert call('POST', '/v1/requests', body)[0] == 503
            assert call('POST', '/v1/workspaces', {}, auth=False)[0] == 401
            stop()
            start(restored, 503)
            assert call('POST', '/v1/requests', body)[0] == 503
        finally:
            stop()
    print(json.dumps({'schema': 'nexus.local-pilot-acceptance.v1', 'status': 'PASS',
        'scope': 'disposable-synthetic-data-only', 'post_202_with_id': True,
        'get_pending': True, 'restart_preserved_workspace_and_request': True,
        'duplicate_409': True, 'restored_reads_preserved': True,
        'restored_writes_503': True, 'quarantine_survives_restart': True,
        'unauthenticated_workspace_401': True, 'production_data_recovered': False,
        'private_api_no_store': True,
        'authority': 'none', 'seal_readiness': False}, sort_keys=True))


if __name__ == '__main__':
    main()
