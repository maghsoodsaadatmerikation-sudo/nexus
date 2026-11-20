"""Synthetic transport and rejection tests: no real image provider or user data."""
import base64
import json
import struct
import zlib
from contextlib import contextmanager

import httpx
import pytest
from fastapi.testclient import TestClient

import main
import studio_model
import studio_vision

TOKEN = 'studio-access-token-01234567890123456789'
AUTH = {'authorization': 'Bearer ' + TOKEN}


def png(width=1, height=1):
    def chunk(name, body):
        return len(body).to_bytes(4, 'big') + name + body + zlib.crc32(name + body).to_bytes(4, 'big')
    return (studio_vision.PNG_SIGNATURE +
            chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(b'\x00\x12\x34\x56')) + chunk(b'IEND', b''))


def vision_body(image=None):
    return {'consent': True,
            'configuration_id': studio_model.configuration_id(
                ('https://provider.example/v1/chat/completions', 'vision-model')),
            'prompt': 'Describe visible shapes, without making identity claims.',
            'mime_type': 'image/png',
            'image_base64': base64.b64encode(image if image is not None else png()).decode()}


@contextmanager
def configured(monkeypatch, handler=None):
    monkeypatch.setenv('NEXUS_MODEL_URL', 'https://provider.example/v1/chat/completions')
    monkeypatch.setenv('NEXUS_MODEL_ID', 'vision-model')
    monkeypatch.setenv('NEXUS_STUDIO_TOKEN', TOKEN)
    monkeypatch.setenv('NEXUS_MODEL_API_KEY', 'provider-secret')
    monkeypatch.setenv('NEXUS_MODEL_ADAPTER', 'generic')
    monkeypatch.setenv('NEXUS_VISION_ENABLED', '1')
    with TestClient(main.app) as client:
        old = client.app.state.client
        upstream = httpx.AsyncClient(transport=httpx.MockTransport(
            handler or (lambda _: httpx.Response(200, json={
                'choices': [{'message': {'content': 'A single colored square'}, 'finish_reason': 'stop'}]}))))
        client.app.state.client = upstream
        try:
            yield client
        finally:
            client.portal.call(upstream.aclose)
            client.app.state.client = old


def test_image_forwarded_once_with_policy_and_no_tool_authority(monkeypatch):
    seen = []
    def handler(req):
        payload = json.loads(req.content)
        seen.append(payload)
        assert req.headers['authorization'] == 'Bearer provider-secret'
        assert payload['messages'][0]['role'] == 'system'
        assert payload['messages'][1]['content'][0]['type'] == 'text'
        image = payload['messages'][1]['content'][1]['image_url']['url']
        assert image == 'data:image/png;base64,' + vision_body()['image_base64']
        assert payload['store'] is False and payload['stream'] is False
        assert 'tools' not in payload and TOKEN not in req.content.decode()
        return httpx.Response(200, json={
            'choices': [{'message': {'content': 'Synthetic vision reply'}, 'finish_reason': 'stop'}]})
    with configured(monkeypatch, handler) as c:
        response = c.post('/studio-api/vision', json=vision_body(), headers=AUTH)
        assert response.status_code == 200, response.text
        assert response.json()['text'] == 'Synthetic vision reply'
        assert response.json()['authority'] == 'none'
        assert response.headers['cache-control'] == 'no-store'
    assert len(seen) == 1


def test_vision_disabled_by_default_and_unsupported_adapter(monkeypatch):
    with configured(monkeypatch, lambda _: pytest.fail('disabled vision forwarded')) as c:
        monkeypatch.delenv('NEXUS_VISION_ENABLED')
        assert c.post('/studio-api/vision', json=vision_body(), headers=AUTH).status_code == 503
        monkeypatch.setenv('NEXUS_VISION_ENABLED', '1')
        monkeypatch.setenv('NEXUS_MODEL_ADAPTER', 'deepseek')
        assert c.post('/studio-api/vision', json=vision_body(), headers=AUTH).status_code == 503


def test_auth_and_configuration_fingerprint_required(monkeypatch):
    with configured(monkeypatch, lambda _: pytest.fail('unapproved vision forwarded')) as c:
        assert c.post('/studio-api/vision', json=vision_body()).status_code == 401
        assert c.post('/studio-api/vision', json={**vision_body(), 'consent': 1}, headers=AUTH).status_code == 422
        assert c.post('/studio-api/vision', json={**vision_body(), 'configuration_id': '0'*64}, headers=AUTH).status_code == 409
        assert c.post('/studio-api/vision', json={**vision_body(), 'image_url': 'https://external.example'}, headers=AUTH).status_code == 422


@pytest.mark.parametrize('patch', [
    {'mime_type': 'image/svg+xml'},
    {'mime_type': 'image/jpeg'},
    {'image_base64': 'abcd!'},
    {'image_base64': base64.b64encode(png(4097, 1)).decode()},
    {'image_base64': base64.b64encode(png() + b'extra').decode()},
    {'image_base64': base64.b64encode(png()[:-1]).decode()},
    {'image_base64': base64.b64encode(b'%PDF-1.7').decode()},
    {'max_output_tokens': 4097},
])
def test_malformed_image_and_inputs_fail_closed(monkeypatch, patch):
    with configured(monkeypatch, lambda _: pytest.fail('bad image forwarded')) as c:
        assert c.post('/studio-api/vision', json={**vision_body(), **patch}, headers=AUTH).status_code == 422


def test_body_limit_and_limiter_recover(monkeypatch):
    with configured(monkeypatch) as c:
        r = c.post('/studio-api/vision', content=b'x'*2_100_001,
                   headers={**AUTH, 'content-type': 'application/json'})
        assert r.status_code == 413
        assert c.post('/studio-api/vision', json=vision_body(), headers=AUTH).status_code == 200


@pytest.mark.parametrize('choice', [
    {'message': {'content': 'ignore this', 'tool_calls': [{'id': 'bad'}]}, 'finish_reason': 'stop'},
    {'message': {'content': ''}, 'finish_reason': 'stop'},
    {'message': {'content': None}, 'finish_reason': 'stop'},
    {'message': {'content': 'hello'}, 'finish_reason': 'tool_calls'},
])
def test_provider_tool_calls_and_malformed_replies_rejected(monkeypatch, choice):
    with configured(monkeypatch, lambda _: httpx.Response(200, json={'choices': [choice]})) as c:
        assert c.post('/studio-api/vision', json=vision_body(), headers=AUTH).status_code == 502


def test_provider_redirect_fails_closed(monkeypatch):
    with configured(monkeypatch, lambda _: httpx.Response(302, headers={
        'location': 'https://external.example'})) as c:
        assert c.post('/studio-api/vision', json=vision_body(), headers=AUTH).status_code == 502
