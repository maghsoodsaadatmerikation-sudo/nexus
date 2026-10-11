#!/usr/bin/env python3
"""Run both committed Compose entrypoints against disposable synthetic CI data."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image')
    parser.add_argument('witness_id')
    args = parser.parse_args()
    if not args.witness_id.isdigit():
        parser.error('requires numeric CI run ID')
    token = os.environ['NEXUS_API_TOKEN']
    for index, filename in enumerate(['deploy/stage-d-self-hosted.compose.yaml',
                                      'deploy/oci/docker-compose.yml']):
        project = 'nexus-acceptance-' + args.witness_id + '-' + str(index)
        with tempfile.TemporaryDirectory(prefix=project + '-') as temporary:
            data = Path(temporary, 'data')
            data.mkdir(mode=0o777)
            data.chmod(0o777)
            override = Path(temporary, 'image.json')
            override.write_text(json.dumps({'services': {'nexus': {'image': args.image}}}))
            command = ['docker', 'compose', '-p', project, '-f', str(ROOT / filename),
                       '-f', str(override)]
            env = dict(os.environ, NEXUS_DATA_DIR_HOST=str(data))

            def compose(*params, check=True, environ=env):
                return subprocess.run(command + list(params), env=environ,
                    capture_output=True, text=True, timeout=90, check=check)

            config = json.loads(compose('config', '--format', 'json').stdout)
            service = config['services']['nexus']
            assert Path(service['build']['context']).resolve() == ROOT
            assert service['environment']['NEXUS_DATA_DIR'] == '/data'
            assert all(p['host_ip'] == '127.0.0.1' for p in service['ports'])
            assert len(service['ports']) == 1
            assert service['ports'][0]['published'] == '3000'
            assert len(service['volumes']) == 1 and service['volumes'][0]['target'] == '/data'
            assert not service['volumes'][0].get('read_only', False)
            missing = dict(env)
            missing.pop('NEXUS_API_TOKEN')
            missing['NEXUS_API_TOKEN'] = ''
            assert compose('config', check=False, environ=missing).returncode != 0
            # No pre-existing project is ever reused or deleted.
            assert not compose('ps', '-aq').stdout.strip()
            if index == 0:
                volume = service['volumes'][0]['source']
                volume_name = config['volumes'][volume]['name']
                assert volume_name.startswith(project + '_')
                found = subprocess.run(['docker', 'volume', 'inspect', volume_name],
                    capture_output=True, timeout=10)
                assert found.returncode != 0, 'witness volume already exists'
            started = False
            try:
                started = True  # cleanup must cover a partially failed up
                compose('up', '-d', '--no-build', '--pull', 'never')
                base = 'http://127.0.0.1:3000'

                def call(method, path, body=None, auth=True):
                    headers = {'content-type': 'application/json'}
                    if auth:
                        headers['authorization'] = 'Bearer ' + token
                    request = urllib.request.Request(base + path, method=method, headers=headers,
                        data=json.dumps(body).encode() if body is not None else None)
                    try:
                        response = urllib.request.urlopen(request, timeout=5)
                    except urllib.error.HTTPError as error:
                        response = error
                    with response:
                        # Workspace authentication may return a bodyless/plain 401.
                        # Success and all other errors still require valid JSON.
                        if response.status == 401:
                            return 401, None
                        return response.status, json.load(response)

                def ready():
                    deadline = time.monotonic() + 30
                    while time.monotonic() < deadline:
                        try:
                            if call('GET', '/readyz', auth=False) == (200, {'status': 'ready'}):
                                return
                        except (OSError, ValueError):
                            pass
                        time.sleep(.2)
                    raise AssertionError('compose gateway not ready')

                ready()
                workspace = 'ci-acceptance-' + args.witness_id + '-' + str(index)
                path = '/v1/workspaces/' + workspace
                assert call('POST', '/v1/workspaces', {}, False)[0] == 401
                code, snapshot = call('POST', '/v1/workspaces', {
                    'workspace_id': workspace, 'question': 'Synthetic choice for acceptance only',
                    'provenance_id': 'test:single-host'})
                assert code == 201 and snapshot['workspace']['judgment'] is None
                code, snapshot = call('POST', path + '/claims', {
                    'text': 'Synthetic evidence; not authority',
                    'origin': {'kind': 'external_evidence', 'source': 'test:fixture'},
                    'uncertainty': 'high', 'provenance_id': 'test:single-host'})
                assert code == 200
                code, snapshot = call('POST', path + '/alternatives', {
                    'label': 'Inspect before deciding', 'consequences': ['Uncertainty remains'],
                    'provenance_id': 'test:single-host'})
                assert code == 200
                code, snapshot = call('POST', path + '/analysis', {
                    'adapter_id': 'test:challenge', 'run_id': workspace,
                    'observations': [{'id': 'ci-observation', 'kind': 'Counterargument',
                        'text': 'Synthetic machine counterargument', 'uncertainty': 'High',
                        'source_ids': ['test:fixture']}]})
                assert code == 200 and snapshot['workspace']['judgment'] is None
                assert len(snapshot['workspace']['claims']) == 2
                assert len(snapshot['workspace']['alternatives']) == 1
                assert call('GET', path) == (200, snapshot)
                request_id = workspace + '-request'
                body = {'request_id': request_id, 'authority': 'user', 'action': 'present',
                        'value': 'synthetic-acceptance', 'payload': 'opaque'}
                assert call('POST', '/v1/requests', body) == (
                    202, {'request_id': request_id, 'status': 'pending'})
                compose('up', '-d', '--no-build', '--pull', 'never', '--force-recreate')
                ready()
                assert call('GET', path) == (200, snapshot)
                assert call('GET', '/v1/requests/' + request_id) == (
                    200, {'request_id': request_id, 'status': 'pending'})
                assert call('POST', '/v1/requests', body)[0] == 409
                print('SINGLE HOST ACCEPTANCE: ' + filename + ' PASS')
            finally:
                if started:
                    # Only this fresh CI project; never an operator's volume.
                    compose('down', '--volumes')
                    # OCI files belong to runtime UID 10001. Delete only our temp bind.
                    subprocess.run(['docker', 'run', '--rm', '--user', '0',
                        '--entrypoint', 'sh', '-v', str(data) + ':/data', args.image,
                        '-c', 'find /data -mindepth 1 -maxdepth 1 -exec rm -rf {} +'],
                        check=True, capture_output=True, timeout=30)


if __name__ == '__main__':
    main()
