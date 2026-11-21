"""Synthetic, no-network image generation contract tests."""
import base64
import json
import struct
import zlib
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import httpx
import pytest
from fastapi.testclient import TestClient

import main
import studio_image_generation as images

TOKEN = 'studio-access-token-01234567890123456789'
KEY = 'provider-key-do-not-leak'


def one_pixel():
    def chunk(name, data):
        return len(data).to_bytes(4, 'big') + name + data + zlib.crc32(name + data).to_bytes(4, 'big')
    return (b'\x89PNG\r\n\x1a\n' +
            chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(b'\x00\x12\x34\x56')) + chunk(b'IEND', b''))


PNG64 = base64.b64encode(one_pixel()).decode('ascii')


def body():
    return {'consent': True, 'configuration_id': images.configuration_id(images.config()),
            'prompt': 'An original purple-green geometric landscape', 'size': '1024x1024'}


@contextmanager
def configured(monkeypatch, handler=None):
    monkeypatch.setenv('NEXUS_IMAGE_ENABLED', '1')
    monkeypatch.setenv('NEXUS_IMAGE_WIRE_FORMAT', 'gpt')
    monkeypatch.setenv('NEXUS_IMAGE_URL', 'https://provider.example/v1/images/generations')
    monkeypatch.setenv('NEXUS_IMAGE_MODEL', 'synthetic-image-model')
    monkeypatch.setenv('NEXUS_IMAGE_API_KEY', KEY)
    monkeypatch.setenv('NEXUS_STUDIO_TOKEN', TOKEN)
    monkeypatch.setenv('NEXUS_IMAGE_MAX_REQUESTS_PER_PROCESS', '20')
    default = lambda _: httpx.Response(200, json={'data': [{'b64_json': PNG64}]})
    with TestClient(main.app) as c:
        old = c.app.state.client
        upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler or default))
        c.app.state.client = upstream
        try:
            yield c
        finally:
            c.portal.call(upstream.aclose)
            c.app.state.client = old


def test_routes_are_part_of_cloud_adapter():
    routes = {route.path for route in main.app.routes}
    assert {'/studio-api/image-generation-status', '/studio-api/generate-image'} <= routes


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv('NEXUS_IMAGE_ENABLED', raising=False)
    with TestClient(main.app) as c:
        assert c.get('/studio-api/image-generation-status').json()['configured'] is False
        assert c.post('/studio-api/generate-image', json={'prompt': 'cat'}).status_code == 503


def test_one_reviewed_image_only_and_no_secret_leak(monkeypatch):
    calls = []
    def provider(request):
        calls.append(request)
        payload = json.loads(request.content)
        assert request.url == 'https://provider.example/v1/images/generations'
        assert request.headers['authorization'] == 'Bearer ' + KEY
        assert payload == {'model': 'synthetic-image-model',
                           'prompt': 'An original purple-green geometric landscape',
                           'size': '1024x1024', 'n': 1, 'output_format': 'png'}
        assert TOKEN not in request.content.decode('utf-8')
        return httpx.Response(200, json={'data': [{'b64_json': PNG64}]})
    with configured(monkeypatch, provider) as c:
        status = c.get('/studio-api/image-generation-status')
        assert status.status_code == 200 and status.headers['cache-control'] == 'no-store'
        assert status.json()['configured'] is True
        assert status.json()['provider_host'] == 'provider.example'
        assert status.json()['authority'] == 'none'
        assert TOKEN not in status.text and KEY not in status.text
        response = c.post('/studio-api/generate-image', json=body(),
                          headers={'authorization': 'Bearer ' + TOKEN})
        assert response.status_code == 200, response.text
        assert response.headers['cache-control'] == 'no-store'
        assert response.json() == {'image_base64': PNG64, 'mime_type': 'image/png',
                                   'model': 'synthetic-image-model', 'authority': 'none',
                                   'storage': 'not-retained-by-nexus'}
        assert TOKEN not in response.text and KEY not in response.text
    assert len(calls) == 1


def test_unapproved_requests_never_contact_provider(monkeypatch):
    with configured(monkeypatch, lambda _: pytest.fail('unapproved request went upstream')) as c:
        good = body()
        auth = {'authorization': 'Bearer ' + TOKEN}
        assert c.post('/studio-api/generate-image', json=good).status_code == 401
        assert c.post('/studio-api/generate-image', json={**good, 'consent': 1}, headers=auth).status_code == 422
        assert c.post('/studio-api/generate-image', json={**good, 'consent': False}, headers=auth).status_code == 422
        assert c.post('/studio-api/generate-image', json={**good, 'prompt': ' \n  '}, headers=auth).status_code == 422
        assert c.post('/studio-api/generate-image', json={**good, 'size': '4000x4000'}, headers=auth).status_code == 422
        assert c.post('/studio-api/generate-image', json={**good, 'image_url': 'https://evil.example'}, headers=auth).status_code == 422
        assert c.post('/studio-api/generate-image', json={**good, 'configuration_id': '0'*64}, headers=auth).status_code == 409
        assert c.post('/studio-api/generate-image', content=b'1'*10_001,
                      headers={**auth, 'content-type': 'application/json'}).status_code == 413


@pytest.mark.parametrize('endpoint', [
    'http://provider.example/v1/images/generations',
    'https://user:pass@provider.example/v1/images/generations',
    'https://provider.example/v1/images/generations?q=secret',
    'https://provider.example/v1/chat/completions',
    'https://provider.example:99999/v1/images/generations',
])
def test_insecure_provider_endpoint_fails_closed(monkeypatch, endpoint):
    with configured(monkeypatch, lambda _: pytest.fail('unsafe endpoint contacted')) as c:
        monkeypatch.setenv('NEXUS_IMAGE_URL', endpoint)
        assert c.get('/studio-api/image-generation-status').json()['configured'] is False
        assert c.post('/studio-api/generate-image', json={'prompt': 'x'}).status_code == 503


@pytest.mark.parametrize('bad', [None, '0', '1001', 'unlimited', '2.0', ' 2 '])
def test_missing_or_invalid_quota_fails_closed(monkeypatch, bad):
    with configured(monkeypatch, lambda _: pytest.fail('unbudgeted image request')) as c:
        if bad is None:
            monkeypatch.delenv('NEXUS_IMAGE_MAX_REQUESTS_PER_PROCESS')
        else:
            monkeypatch.setenv('NEXUS_IMAGE_MAX_REQUESTS_PER_PROCESS', bad)
        assert c.get('/studio-api/image-generation-status').json()['configured'] is False
        assert c.post('/studio-api/generate-image', json=body(),
                      headers={'authorization': 'Bearer ' + TOKEN}).status_code == 503


def test_quota_counts_failed_provider_attempt_and_not_invalid_requests(monkeypatch):
    count = []
    def provider(request):
        count.append(request)
        return httpx.Response(503) if len(count) == 1 else httpx.Response(200, json={'data': [{'b64_json': PNG64}]})
    with configured(monkeypatch, provider) as c:
        monkeypatch.setenv('NEXUS_IMAGE_MAX_REQUESTS_PER_PROCESS', '2')
        auth = {'authorization': 'Bearer ' + TOKEN}
        good = body()
        assert c.post('/studio-api/generate-image', json={**good, 'size': 'bad'}, headers=auth).status_code == 422
        assert c.post('/studio-api/generate-image', json=good, headers=auth).status_code == 502
        assert c.post('/studio-api/generate-image', json=good, headers=auth).status_code == 200
        assert c.post('/studio-api/generate-image', json=good, headers=auth).status_code == 429
        assert c.get('/studio-api/image-generation-status').json()['reason'] == 'limit-reached'
    assert len(count) == 2


@pytest.mark.parametrize('provider', [
    lambda _: httpx.Response(302, headers={'location': 'https://evil.example'}),
    lambda _: httpx.Response(200, json={'data': [{'url': 'https://evil.example/image.png'}]}),
    lambda _: httpx.Response(200, json={'data': []}),
    lambda _: httpx.Response(200, json={'data': [{'b64_json': '!!!'}]}),
    lambda _: httpx.Response(200, json={'data': [{'b64_json': base64.b64encode(b'<svg/>').decode()}]}),
    lambda _: httpx.Response(200, content=b'Z'*9_000_001),
])
def test_malformed_or_unbounded_provider_outputs_rejected(monkeypatch, provider):
    with configured(monkeypatch, provider) as c:
        r = c.post('/studio-api/generate-image', json=body(),
                   headers={'authorization': 'Bearer ' + TOKEN})
        assert r.status_code == 502


def test_key_rotation_invalidates_prepared_review(monkeypatch):
    with configured(monkeypatch, lambda _: pytest.fail('stale review contacted provider')) as c:
        prepared = body()
        monkeypatch.setenv('NEXUS_IMAGE_API_KEY', 'new-image-provider-secret')
        r = c.post('/studio-api/generate-image', json=prepared,
                   headers={'authorization': 'Bearer ' + TOKEN})
        assert r.status_code == 409


def test_quota_atomic_across_threads():
    quota = images.ProcessQuota()
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda _: quota.reserve(6), range(120)))
    assert sum(results) == 6
    assert quota.remaining(6) == 0


def test_legacy_provider_mode_and_review_rotation(monkeypatch):
    captured = []
    def handler(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={'data': [{'b64_json': PNG64}]})
    with configured(monkeypatch, handler) as c:
        modern_review = body()
        monkeypatch.setenv('NEXUS_IMAGE_WIRE_FORMAT', 'legacy')
        auth = {'authorization': 'Bearer ' + TOKEN}
        assert c.post('/studio-api/generate-image', json=modern_review, headers=auth).status_code == 409
        assert c.post('/studio-api/generate-image', json=body(), headers=auth).status_code == 200
    assert captured[0]['response_format'] == 'b64_json'
    assert 'output_format' not in captured[0]
