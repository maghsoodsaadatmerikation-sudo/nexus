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
    def __init__(self, code, body=b''):
        super().__init__(body)
        self.code = code


class RuntimeTests(unittest.TestCase):
    def run_observation(self, digest=DIGEST, overrides=None):
        calls = []
        overrides = overrides or {}
        def open_request(request, timeout):
            calls.append(request)
            path = observer.urllib.parse.urlsplit(request.full_url).path
            if path in overrides:
                code, body = overrides[path]
            elif path == '/v1/runtime-identity':
                code, body = 200, json.dumps({'schema': 'nexus.runtime-identity.v1',
                    'authority': 'non_authoritative_build_metadata',
                    'source_tree_sha256': digest}).encode()
            else:
                code, body = (200 if path in ('/livez', '/readyz') else 401), b''
            return Response(code, body)
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
        r = self.run_observation(overrides={'/readyz': (503, b''), '/v1/workspaces': (200, b'private')})
        self.assertIn('readyz_not_200', r['blockers'])
        self.assertIn('unauthenticated_get_not_401:/v1/workspaces', r['blockers'])
        self.assertNotIn('private', json.dumps(r))

    def test_identity_bounded_and_malformed(self):
        for body in (b'x' * (observer.LIMIT + 1), b'[]', b'{', b'\xff'):
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
