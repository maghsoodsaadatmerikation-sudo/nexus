"""No tests in this module perform network access."""
from __future__ import annotations

import io
import json
from urllib.error import URLError

import pytest
from agent_research import ResearchDenied, endpoint, fetch_metadata, MAX_REMOTE_BYTES


class FakeResponse:
    status = 200
    def __init__(self, url, body, *, headers=None, status=200, redirect_to=None):
        self.url = redirect_to or url
        self.stream = io.BytesIO(body)
        self.status = status
        self.headers = {"Content-Type": "application/json", **(headers or {})}
    def geturl(self):
        return self.url
    def read(self, n=-1):
        return self.stream.read(n)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


def fixture_reply(provider, name, payload, **options):
    calls = []
    raw = json.dumps(payload).encode()
    def factory(req, timeout):
        calls.append((req, timeout))
        return FakeResponse(req.full_url, raw, **options)
    return factory, calls


@pytest.mark.parametrize("provider,name,url", [
    ("pypi", "httpx", "https://pypi.org/pypi/httpx/json"),
    ("crates", "serde", "https://crates.io/api/v1/crates/serde"),
    ("github-release", "astral-sh/uv", "https://api.github.com/repos/astral-sh/uv/releases/latest"),
])
def test_fixed_endpoint(provider, name, url):
    assert endpoint(provider, name) == url


@pytest.mark.parametrize("provider,name", [
    ("pypi", "../secret"), ("pypi", ".."), ("pypi", "a/b"),
    ("pypi", "http://evil.test/"), ("pypi", "x?token=1"),
    ("crates", "a#fragment"), ("crates", " space"),
    ("github-release", "../repo"), ("github-release", "owner/.."),
    ("github-release", "owner/repo/other"), ("github-release", "owner/repo?x=1"),
    ("github-release", "owner@evil/repo"), ("not-supported", "foo"),
    ("pypi", "a"*129),
])
def test_invalid_target_rejected_before_network(provider, name):
    with pytest.raises(ResearchDenied):
        endpoint(provider, name)


@pytest.mark.parametrize("provider,name,payload,version", [
    ("pypi", "httpx", {"info": {"name": "httpx", "version": "1.2.3"}}, "1.2.3"),
    ("crates", "serde", {"crate": {"id": "serde", "max_version": "1.0.240"}}, "1.0.240"),
    ("github-release", "astral-sh/uv", {"name": "New release", "tag_name": "v0.9.1"}, "v0.9.1"),
])
def test_approved_fixed_provider_metadata_is_untrusted(provider, name, payload, version):
    opener, calls = fixture_reply(provider, name, payload)
    item = fetch_metadata(provider, name, open_request=opener)
    assert item["version"] == version
    assert item["provenance"] == "external-provider-metadata-unverified"
    assert len(item["source_sha256"]) == 64 and item["source_url"] == endpoint(provider, name)
    assert item["retrieved_at"].endswith("+00:00")
    assert len(calls) == 1 and calls[0][1] == 8.0
    req = calls[0][0]
    assert req.get_method() == "GET" and req.full_url == endpoint(provider, name)
    assert not any(x.lower() in ("cookie", "authorization") for x in req.headers)


@pytest.mark.parametrize("options", [
    {"status": 404},
    {"redirect_to": "https://example.com/escape"},
    {"headers": {"Content-Type": "text/html"}},
    {"headers": {"Content-Length": str(MAX_REMOTE_BYTES + 1)}},
    {"headers": {"Content-Length": "not-a-number"}},
])
def test_bad_source_never_accepted_as_verified(options):
    opener, _ = fixture_reply("pypi", "httpx", {"info": {"name": "httpx", "version": "1"}}, **options)
    with pytest.raises(ResearchDenied):
        fetch_metadata("pypi", "httpx", open_request=opener)


def test_bounded_streaming_rejects_large_json_without_declared_length():
    def opener(req, timeout):
        return FakeResponse(req.full_url, b"{" + b" "*MAX_REMOTE_BYTES + b"}")
    with pytest.raises(ResearchDenied, match="research-size"):
        fetch_metadata("pypi", "httpx", open_request=opener)


@pytest.mark.parametrize("body", [b"not-json", b"[]", b"{}", b'{"info":{"name":"x"}}', b'\xff'])
def test_invalid_metadata_denied(body):
    def opener(req, timeout):
        return FakeResponse(req.full_url, body)
    with pytest.raises(ResearchDenied):
        fetch_metadata("pypi", "httpx", open_request=opener)


def test_failed_network_never_produces_fabricated_answer():
    def opener(req, timeout):
        raise URLError("offline")
    with pytest.raises(ResearchDenied, match="research-unavailable"):
        fetch_metadata("pypi", "httpx", open_request=opener)
