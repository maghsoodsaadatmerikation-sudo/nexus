#!/usr/bin/env python3
"""Synthetic-only Stage D operator transport security tests; no real credentials."""
import importlib.util
from email.message import Message
import io
from pathlib import Path
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "ops" / "stage_d_transport.py"
spec = importlib.util.spec_from_file_location("stage_d_transport", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
FAKE_TOKEN = "SYNTHETIC-SECRET-SENTINEL"


class Response:
    def __init__(self, status=200, body=b'{"workspace":{"id":"test"}}', headers=None):
        self.status = status
        self.code = status
        self.stream = io.BytesIO(body)
        self.headers = Message()
        headers = ({"Content-Type": "application/json", "Cache-Control": "no-store",
                    "Content-Length": str(len(body))} if headers is None else headers)
        for key, value in headers.items():
            for item in value if isinstance(value, list) else [value]:
                self.headers.add_header(key, item)

    def read(self, count):
        return self.stream.read(count)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()


class Opener:
    def __init__(self, response=None, error=None):
        self.response = Response() if response is None else response
        self.error = error
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        if self.error is not None:
            raise self.error
        return self.response


class TransportTests(unittest.TestCase):
    def call(self, *, base="https://stage.example", route="/v1/workspaces/test",
             method="GET", token=FAKE_TOKEN, body=None, response=None, error=None):
        opener = Opener(response, error)
        return module.request(base, route, method, body, token, opener=opener), opener

    def blocked(self, **kwargs):
        with self.assertRaises(module.TransportBlocked) as caught:
            self.call(**kwargs)
        self.assertNotIn(FAKE_TOKEN, str(caught.exception))
        self.assertNotIn("stage.example", str(caught.exception))

    def test_bearer_only_in_private_request_header_not_url_or_argv(self):
        (status, body), opener = self.call()
        self.assertEqual(status, 200)
        self.assertEqual(body, b'{"workspace":{"id":"test"}}')
        req, timeout = opener.requests[0]
        self.assertEqual(req.full_url, "https://stage.example/v1/workspaces/test")
        self.assertEqual(req.get_header("Authorization"), "Bearer " + FAKE_TOKEN)
        self.assertIsNone(req.data)
        self.assertEqual(timeout, module.TIMEOUT_SECONDS)

    def test_post_has_json_payload_and_mandatory_authentication(self):
        (_, _), opener = self.call(route="/v1/workspaces", method="POST", body={"x": 1})
        req, _ = opener.requests[0]
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.data, b'{"x":1}')
        self.blocked(route="/v1/workspaces", method="POST", token=None, body={"x": 1})

    def test_unauthenticated_public_root_and_private_probe(self):
        (_, _), opener = self.call(token=None)
        self.assertFalse(opener.requests[0][0].has_header("Authorization"))
        (_, _), opener = self.call(route="/", token=None, response=Response(body=b"<html>ok</html>"))
        self.assertFalse(opener.requests[0][0].has_header("Authorization"))

    def test_reject_bad_origin_before_any_network_call(self):
        bad = ("http://stage.example", "https://user:password@stage.example",
               "https://stage.example/path", "https://stage.example?token=s",
               "https://stage.example#fragment", "https://stage.example:8443",
               "https://stage.example:bad", "https://[invalid",
               "https://stage.example\\r\\nX-Injection: true", "")
        for base in bad:
            with self.subTest(base=base):
                self.blocked(base=base)

    def test_reject_foreign_routes_and_unsafe_methods(self):
        paths = ("//foreign.example/", "/v1/workspaces/test?query=x",
                 "/v1/workspaces/../secret", "/v1/requests",
                 "/v1/workspaces/test/claims", "https://foreign.example/",
                 "/v1/workspaces/مریم", "/v1/workspaces/import")
        for route in paths:
            with self.subTest(route=route):
                self.blocked(route=route)
        for method in ("DELETE", "PUT", "PATCH", "HEAD"):
            self.blocked(method=method)
        self.blocked(body={"invalid": True})

    def test_reject_unsafe_bearer_values(self):
        for token in ("", "a b", "a\\r\\nX-Injected: true", "x" * 4097, 1):
            with self.subTest(token=str(token)[:10]):
                self.blocked(token=token)

    def test_redirect_handler_never_forwards_bearer(self):
        req = urllib.request.Request("https://stage.example/test",
                                     headers={"Authorization": "Bearer " + FAKE_TOKEN})
        for status in (301, 302, 303, 307, 308):
            self.assertIsNone(module.NoRedirect().redirect_request(
                req, None, status, "redirect", {}, "https://foreign.example/collector"))
        self.blocked(response=Response(status=302))
        self.blocked(error=urllib.error.HTTPError(
            "https://stage.example/test", 302, "redirect", Message(), io.BytesIO(b"secret")))

    def test_transport_installs_no_proxy_and_no_redirect_policy(self):
        seen = []
        def build(*handlers):
            seen.extend(handlers)
            return Opener()
        with patch.object(module.urllib.request, "build_opener", build):
            module.request("https://stage.example", "/v1/workspaces/test", token=FAKE_TOKEN)
        self.assertTrue(any(isinstance(x, module.NoRedirect) for x in seen))
        self.assertEqual(next(x for x in seen if isinstance(x, urllib.request.ProxyHandler)).proxies, {})

    def test_bounded_body_and_reject_mismatched_or_duplicate_lengths(self):
        for response in (
            Response(body=b"x" * (module.MAX_RESPONSE + 1),
                     headers={"Content-Type": "application/json", "Cache-Control": "no-store"}),
            Response(body=b"{}",
                     headers={"Content-Type": "application/json", "Cache-Control": "no-store",
                              "Content-Length": str(module.MAX_RESPONSE + 1)}),
            Response(body=b"{}",
                     headers={"Content-Type": "application/json", "Cache-Control": "no-store",
                              "Content-Length": ["2", "2"]}),
            Response(body=b"{}",
                     headers={"Content-Type": "application/json", "Cache-Control": "no-store",
                              "Content-Length": "4"}),
        ):
            with self.subTest(response=response):
                self.blocked(response=response)

    def test_invalid_private_headers_block(self):
        for headers in (
            {"Content-Type": "application/json"},
            {"Content-Type": "text/html", "Cache-Control": "no-store"},
            {"Content-Type": "application/json", "Cache-Control": "max-age=300"},
        ):
            self.blocked(response=Response(headers=headers))

    def test_invalid_or_ambiguous_json_blocks(self):
        for raw in (b"{}{}", b"[]", b"null", b"NaN", b'{"a":1,"a":2}', b"\\xff"):
            with self.subTest(raw=raw):
                self.blocked(response=Response(body=raw))

    def test_transport_exception_never_exposes_bearer_or_url(self):
        self.blocked(error=urllib.error.URLError(FAKE_TOKEN))

    def test_private_401_is_reported_only_with_valid_json_and_no_store(self):
        (status, body), _ = self.call(response=Response(
            status=401, body=b'{"error":"transport_authentication_required"}'))
        self.assertEqual(status, 401)
        self.assertEqual(body, b'{"error":"transport_authentication_required"}')

    def test_invalid_json_or_oversized_request_rejected(self):
        self.blocked(route="/v1/workspaces", method="POST", body={"x": float("nan")})
        self.blocked(route="/v1/workspaces", method="POST",
                     body={"x": "x" * (module.MAX_REQUEST + 1)})

    def test_operator_entrypoint_uses_transport_wrapper(self):
        source = (SOURCE.parent / "stage_d_operator.py").read_text()
        self.assertIn("stage_d_transport.request(BASE, path, method, body, token)", source)
        self.assertNotIn("urllib.request.urlopen(", source)
        self.assertIn("stage_d_transport.origin(os.environ", source)


if __name__ == "__main__":
    unittest.main()
