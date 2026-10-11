#!/usr/bin/env python3
"""ENOSPC witness on a disposable 8 MiB Docker tmpfs, never a host volume."""
import argparse
import json
import os
import subprocess
import time
import urllib.error
import urllib.request


def docker(*args, check=True):
    return subprocess.run(['docker', *args], check=check, capture_output=True, text=True, timeout=45)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image')
    parser.add_argument('witness_id')
    args = parser.parse_args()
    if not args.witness_id.isdigit():
        parser.error('witness_id must be a numeric CI run ID')
    name = 'nexus-enospc-' + args.witness_id
    token = os.environ['NEXUS_API_TOKEN']
    created = False
    try:
        # A private tmpfs bounds filling to 8 MiB. No host path or volume mount.
        docker('run', '-d', '--name', name, '--user', '10001:10001',
               '--tmpfs', '/data:rw,size=8m,uid=10001,gid=10001,mode=0700',
               '-p', '127.0.0.1::3000', '-e', 'NEXUS_API_TOKEN',
               '--entrypoint', 'sh', args.image, '-c',
               'while :; do /usr/local/bin/nexus & child=$!; '
               'echo "$child" > /tmp/nexus-gateway.pid; wait "$child"; done')
        created = True
        address = docker('port', name, '3000/tcp').stdout.strip()
        base = 'http://' + address

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
                return response.status, json.load(response)

        def wait_ready():
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                try:
                    if call('GET', '/livez', auth=False) == (200, {'status': 'alive'}):
                        return
                except (OSError, ValueError):
                    pass
                time.sleep(.2)
            raise AssertionError('gateway listener did not recover')

        def submit(request_id, auth=True):
            return call('POST', '/v1/requests', {'request_id': request_id,
                'authority': 'user', 'action': 'present', 'value': 'synthetic-enospc',
                'payload': 'opaque'}, auth)

        def status(request_id, expected):
            assert call('GET', '/v1/requests/' + request_id) == (
                200, {'request_id': request_id, 'status': expected})

        wait_ready()
        prior, failed, repaired = ['ci-full-' + args.witness_id + '-' + suffix
                                  for suffix in ['prior', 'failed', 'repaired']]
        assert submit(prior) == (202, {'request_id': prior, 'status': 'pending'})
        filled = docker('exec', name, 'sh', '-c',
                        'dd if=/dev/zero of=/data/ci-fill bs=4096 count=4096', check=False)
        assert filled.returncode != 0 and 'No space left on device' in filled.stderr
        assert docker('exec', name, 'df', '-B1', '/data').stdout.splitlines()[-1].split()[3] == '0'
        print('STORAGE FULL: REAL ENOSPC PASS')
        assert submit(failed, auth=False)[0] == 401
        code, body = submit(failed)
        assert code == 503 and body['error'] == 'request_store_unavailable'
        status(failed, 'indeterminate')
        assert submit(failed)[0] == 409
        # tmpfs allows an empty inode, but writing the reservation prefix now fails.
        marker = '/data/requests/' + failed.encode().hex()
        assert docker('exec', name, 'stat', '-c', '%s', marker).stdout.strip() == '0'
        status(prior, 'pending')
        assert call('GET', '/readyz', auth=False) == (200, {'status': 'ready'})
        print('STORAGE FULL: NO FALSE 202 PASS')
        docker('exec', name, 'rm', '/data/ci-fill')
        assert submit(failed)[0] == 409
        assert submit(repaired) == (202, {'request_id': repaired, 'status': 'pending'})
        print('STORAGE FULL: REPAIR PASS')
        # Restart only the child process; restarting the container loses its tmpfs.
        old_pid = docker('exec', name, 'cat', '/tmp/nexus-gateway.pid').stdout.strip()
        assert old_pid.isdigit()
        docker('exec', name, 'kill', '-TERM', old_pid)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if docker('exec', name, 'cat', '/tmp/nexus-gateway.pid').stdout.strip() != old_pid:
                break
            time.sleep(.2)
        else:
            raise AssertionError('supervisor did not restart gateway')
        wait_ready()
        status(prior, 'pending')
        status(repaired, 'pending')
        status(failed, 'indeterminate')
        assert submit(failed)[0] == 409
        assert submit(prior)[0] == 409
        assert submit(repaired)[0] == 409
        print('STORAGE FULL: SAME-MOUNT RESTART PASS')
    finally:
        if created:
            docker('rm', '-f', name)


if __name__ == '__main__':
    main()
