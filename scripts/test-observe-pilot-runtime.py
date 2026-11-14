#!/usr/bin/env python3
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import urllib.error

spec = importlib.util.spec_from_file_location('observer', Path(__file__).with_name('observe-pilot-runtime.py'))
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)
DIGEST = 'a' * 64


class Response(io.BytesIO):
    def __init__(self, code, body=b'', headers=None):
        super().__init__(body)
        self.code = code
        self.headers = headers if headers is not None else {
            'Content-Type': 'application/json',
            'Cache-Control': 'private, no-store',
        }


class RuntimeTests(unittest.TestCase):
    def run_observation(self, digest=DIGEST, overrides=None):
        calls = []
        overrides = overrides or {}
        def open_request(request, timeout):
            calls.append(request)
            path = observer.urllib.parse.urlsplit(request.full_url).path
            if path in overrides:
                args = overrides[path]
            elif path == '/v1/runtime-identity':
                args = (200, json.dumps({'schema': 'nexus.runtime-identity.v1',
                    'authority': 'non_authoritative_build_metadata',
                    'source_tree_sha256': digest}).encode())
            elif path == '/livez':
                args = (200, b'{"status":"alive"}')
            elif path == '/readyz':
                args = (200, b'{"status":"ready"}')
            else:
                args = (401, b'')
            return Response(*args)
        with patch('urllib.request.OpenerDirector.open', side_effect=open_request):
            result = observer.observe('https://example.test', DIGEST)
        self.assertEqual(len(calls), 5)
        self.assertTrue(all(r.get_method() == 'GET' and r.data is None and not r.has_header('Authorization') for r in calls))
        self.assertFalse(result['promotion_ready'])
        self.assertFalse(result['production_mutation'])
        return result

    def test_public_success_never_grants_promotion(self):
        self.assertEqual(self.run_observation()['public_checks'], 'SATISFIED')

    def test_old_runtime_is_blocker(self):
        self.assertIn('candidate_not_observed', self.run_observation('b' * 64)['blockers'])

    def test_quarantine_and_exposed_route(self):
        r = self.run_observation(overrides={'/readyz': (503, b'{"status":"quarantined"}'), '/v1/workspaces': (200, b'private')})
        self.assertIn('readyz_not_200', r['blockers'])
        self.assertIn('unauthenticated_get_not_401:/v1/workspaces', r['blockers'])
        self.assertEqual(r['observations']['/readyz']['health_state'], 'quarantined')
        self.assertNotIn('private', json.dumps(r))


    def test_health_false_green_is_blocked(self):
        for path, state in (('/livez', 'alive'), ('/readyz', 'ready')):
            bad = (
                b'', b'200 OK', b'{}', b'[]', b'{"status":"quarantined"}',
                b'{"status":"' + state.encode() + b'","extra":1}',
                b'{"status":"dead","status":"' + state.encode() + b'"}',
                b'x' * (observer.HEALTH_LIMIT + 1), b'\xff', b'{',
            )
            for body in bad:
                with self.subTest(path=path, body=body[:50]):
                    result = self.run_observation(overrides={path: (200, body)})
                    self.assertIn(path[1:] + '_invalid_body_or_headers', result['blockers'])
                    self.assertNotIn('health_state', result['observations'][path])

    def test_health_wrong_type_or_cache_is_blocked(self):
        for path, state in (('/livez', 'alive'), ('/readyz', 'ready')):
            for headers in (
                {'Content-Type': 'text/html', 'Cache-Control': 'no-store'},
                {'Content-Type': 'application/json', 'Cache-Control': 'public, max-age=300'},
                {'Content-Type': 'application/json'},
                {'Cache-Control': 'no-store'},
            ):
                with self.subTest(path=path, headers=headers):
                    r = self.run_observation(overrides={path: (200, ('{"status":"%s"}' % state).encode(), headers)})
                    self.assertIn(path[1:] + '_invalid_body_or_headers', r['blockers'])

    def test_valid_health_header_variants(self):
        for path, state in (('/livez', 'alive'), ('/readyz', 'ready')):
            r = self.run_observation(overrides={path: (200, ('{"status":"%s"}' % state).encode(),
                {'Content-Type': 'Application/JSON; charset=UTF-8', 'Cache-Control': 'public, NO-STORE'})})
            self.assertEqual(r['public_checks'], 'SATISFIED')

    def test_private_unauthenticated_responses_must_not_be_cached(self):
        for path in ('/v1/workspaces', '/v1/requests/nexus-public-observation'):
            r = self.run_observation(overrides={path: (401, b'ignored private body', {'Cache-Control': 'max-age=60'})})
            self.assertIn('unauthenticated_get_cacheable:' + path, r['blockers'])
            self.assertNotIn('ignored private body', json.dumps(r))

    def test_identity_bounded_and_malformed(self):
        for body in (b'x' * (observer.LIMIT + 1), b'[]', b'{', b'\xff',
                     (b'{"schema":"invalid","schema":"nexus.runtime-identity.v1",'
                      b'"authority":"non_authoritative_build_metadata","source_tree_sha256":"'
                      + DIGEST.encode() + b'"}')):
            with self.subTest(body_length=len(body)):
                self.assertIn('runtime_identity_unverified', self.run_observation(overrides={'/v1/runtime-identity': (200, body)})['blockers'])

    def test_transport_failure(self):
        with patch('urllib.request.OpenerDirector.open', side_effect=urllib.error.URLError('secret')):
            r = observer.observe('https://example.test', DIGEST)
        self.assertEqual(len(r['observations']), 5)
        self.assertNotIn('secret', json.dumps(r))
        self.assertEqual(r['public_checks'], 'BLOCKED')

    def test_reject_credential_or_non_origin_input(self):
        for origin in ('http://example.test', 'https://user:password@example.test',
                       'https://example.test/path', 'https://example.test?token=x',
                       'https://example.test#fragment'):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                observer.observe(origin, DIGEST)

    def test_redirect_is_not_followed(self):
        handler = observer.NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, '', {}, 'https://other.test'))
        self.assertIn('runtime_identity_unverified', self.run_observation(overrides={'/v1/runtime-identity': (302, b'')})['blockers'])


if __name__ == '__main__':
    unittest.main()
