#!/usr/bin/env python3
"""Bounded synthetic missing-ledger HTTP witness; never a production fault injector."""
import argparse
import json
import os
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base_url')
    parser.add_argument('request_id')
    parser.add_argument('phase', choices=['unavailable', 'repaired', 'restarted'])
    args = parser.parse_args()

    def call(method, path, body=None, auth=True):
        headers = {'content-type': 'application/json'}
        if auth:
            headers['authorization'] = 'Bearer ' + os.environ['NEXUS_API_TOKEN']
        request = urllib.request.Request(args.base_url.rstrip('/') + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers, method=method)
        try:
            response = urllib.request.urlopen(request, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def submit(request_id, auth=True):
        return call('POST', '/v1/requests', {'request_id': request_id,
            'authority': 'user', 'action': 'present', 'value': 'synthetic-fault',
            'payload': 'opaque'}, auth)

    def status(request_id, expected):
        assert call('GET', '/v1/requests/' + request_id) == (
            200, {'request_id': request_id, 'status': expected})

    # Exercise the real HTTP listener while CI relocates only its disposable
    # request ledger. Liveness must stay up; readiness must reject new work.
    assert call('GET', '/livez', auth=False) == (200, {'status': 'alive'})
    expected_ready = (503, {'status': 'storage_unavailable'}) if args.phase == 'unavailable' else (
        200, {'status': 'ready'})
    assert call('GET', '/readyz', auth=False) == expected_ready
    failed = args.request_id + '-unavailable'
    repaired = args.request_id + '-repaired'
    if args.phase == 'unavailable':
        assert submit(failed, False)[0] == 401
        code, body = submit(failed)
        assert code == 503 and body['error'] == 'request_store_unavailable'
        status(failed, 'indeterminate')
        assert submit(failed)[0] == 409
    elif args.phase == 'repaired':
        status(failed, 'indeterminate')
        assert submit(failed)[0] == 409
        assert submit(repaired) == (202, {'request_id': repaired, 'status': 'pending'})
        status(repaired, 'pending')
    else:
        status(repaired, 'pending')
        assert submit(repaired)[0] == 409
        assert call('GET', '/v1/requests/' + failed)[0] == 404
        assert submit(failed) == (202, {'request_id': failed, 'status': 'pending'})
        status(failed, 'pending')
    print('STORAGE FAILURE HTTP: ' + args.phase.upper() + ' PASS')


if __name__ == '__main__':
    main()
