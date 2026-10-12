#!/usr/bin/env python3
"""Bounded public GET observations; never authorizes promotion or sends credentials."""
import argparse
import datetime
import json
import re
import urllib.error
import urllib.parse
import urllib.request

LIMIT = 16384


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def observe(base, expected, timeout=10):
    parsed = urllib.parse.urlsplit(base)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or parsed.path not in ('', '/')):
        raise ValueError('base must be an HTTPS origin without credentials, path, query or fragment')
    if not re.fullmatch(r'[0-9a-f]{64}', expected):
        raise ValueError('expected digest must be 64 lowercase hexadecimal characters')
    opener = urllib.request.build_opener(NoRedirect())
    observations = {}
    identity = {}
    for path in ('/v1/runtime-identity', '/livez', '/readyz', '/v1/workspaces',
                 '/v1/requests/nexus-public-observation'):
        record = {'method': 'GET'}
        try:
            request = urllib.request.Request(base.rstrip('/') + path, method='GET')
            try:
                response = opener.open(request, timeout=timeout)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                record['http_status'] = response.code
                if path == '/v1/runtime-identity' and response.code == 200:
                    raw = response.read(LIMIT + 1)
                    if len(raw) > LIMIT:
                        record['error'] = 'identity_size_limit'
                    else:
                        try:
                            candidate = json.loads(raw)
                            if isinstance(candidate, dict):
                                identity = candidate
                            else:
                                record['error'] = 'invalid_identity'
                        except (ValueError, UnicodeError):
                            record['error'] = 'invalid_identity'
        except (urllib.error.URLError, TimeoutError, OSError):
            # Avoid logging URLs, response bodies, credentials or exception details.
            record['error'] = 'transport_error'
        observations[path] = record
    valid = (identity.get('schema') == 'nexus.runtime-identity.v1'
             and identity.get('authority') == 'non_authoritative_build_metadata'
             and isinstance(identity.get('source_tree_sha256'), str)
             and re.fullmatch(r'[0-9a-f]{64}', identity['source_tree_sha256']) is not None)
    match = bool(valid and identity['source_tree_sha256'] == expected)
    blockers = []
    if not valid:
        blockers.append('runtime_identity_unverified')
    elif not match:
        blockers.append('candidate_not_observed')
    for path in ('/livez', '/readyz'):
        if observations[path].get('http_status') != 200:
            blockers.append(path[1:] + '_not_200')
    for path in ('/v1/workspaces', '/v1/requests/nexus-public-observation'):
        if observations[path].get('http_status') != 401:
            blockers.append('unauthenticated_get_not_401:' + path)
    return {'schema': 'nexus.pilot.public-observation.v1',
            'observed_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'origin': base.rstrip('/'), 'expected_source_tree_sha256': expected,
            'observed_source_tree_sha256': identity.get('source_tree_sha256') if valid else None,
            'candidate_digest_match': match, 'observations': observations,
            'public_checks': 'BLOCKED' if blockers else 'SATISFIED', 'blockers': blockers,
            'authenticated_acceptance': 'NOT_PERFORMED',
            'full_data_backup': 'NOT_INSPECTED', 'promotion_ready': False,
            'authority': 'none', 'production_mutation': False,
            'claim_boundary': 'Public GET observations only; matching self-reported metadata is not binary attestation, POST acceptance, backup proof, Verify PASS, Seal or release authority.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', required=True)
    parser.add_argument('--expected-digest', required=True)
    args = parser.parse_args()
    try:
        result = observe(args.origin, args.expected_digest)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True, indent=2))
    return 2 if result['blockers'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
