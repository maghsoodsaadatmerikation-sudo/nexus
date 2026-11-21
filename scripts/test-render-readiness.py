#!/usr/bin/env python3
"""Synthetic no-network acceptance for the Render release readiness probe."""

import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).with_name("check-render-readiness.py")
spec = importlib.util.spec_from_file_location("nexus_render_readiness", MODULE_PATH)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
ORIGIN = "https://nexus.example.org"
URL = ORIGIN + "/readyz"


class Response:
    def __init__(self, *, status=200, headers=None, body=b'{"status":"ready"}',
                 url=URL):
        self.status = status
        self.headers = headers if headers is not None else {
            "content-type": "application/json",
            "cache-control": "no-store",
        }
        self.body = body
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        return self.body[:size]

    def geturl(self):
        return self.url


class Opener:
    def __init__(self, response):
        self.response = response
        self.request = None

    def open(self, request, timeout):
        self.request = request
        assert timeout == 5
        return self.response


class ReadinessTests(unittest.TestCase):
    def test_ready_response_passes_without_credentials(self):
        opener = Opener(Response())
        probe.check_readiness(ORIGIN, opener=opener)
        self.assertEqual(opener.request.full_url, URL)
        self.assertEqual(opener.request.get_method(), "GET")
        self.assertIsNone(opener.request.get_header("Authorization"))

    def test_quarantine_fails(self):
        with self.assertRaises(probe.ReadinessFailure):
            probe.check_readiness(ORIGIN, opener=Opener(
                Response(status=503, body=b'{"status":"quarantined"}')))

    def test_ok_response_with_false_status_fails(self):
        with self.assertRaises(probe.ReadinessFailure):
            probe.check_readiness(ORIGIN, opener=Opener(
                Response(body=b'{"status":"quarantined"}')))

    def test_redirect_never_counts_as_ready(self):
        with self.assertRaises(probe.ReadinessFailure):
            probe.check_readiness(ORIGIN, opener=Opener(
                Response(url="https://different.example.org/readyz")))

    def test_html_and_encoded_responses_fail(self):
        for headers in (
            {"content-type": "text/html", "cache-control": "no-store"},
            {"content-type": "application/json", "cache-control": "no-store",
             "content-encoding": "gzip"},
        ):
            with self.subTest(headers=headers):
                with self.assertRaises(probe.ReadinessFailure):
                    probe.check_readiness(ORIGIN, opener=Opener(Response(headers=headers)))

    def test_missing_no_store_fails(self):
        with self.assertRaises(probe.ReadinessFailure):
            probe.check_readiness(ORIGIN, opener=Opener(
                Response(headers={"content-type": "application/json"})))

    def test_oversized_body_and_declared_length_fail(self):
        for response in (
            Response(body=b" " * 513),
            Response(headers={"content-type": "application/json",
                              "cache-control": "no-store", "content-length": "513"}),
        ):
            with self.assertRaises(probe.ReadinessFailure):
                probe.check_readiness(ORIGIN, opener=Opener(response))

    def test_malformed_or_extra_status_fails(self):
        for body in (b"not-json", b'{"status":"ready","token":"oops"}', b"null"):
            with self.subTest(body=body):
                with self.assertRaises(probe.ReadinessFailure):
                    probe.check_readiness(ORIGIN, opener=Opener(Response(body=body)))

    def test_invalid_live_origin_is_rejected(self):
        invalid = (
            "", "http://nexus.example.org", "https://localhost",
            "https://127.0.0.1", "https://user:secret@nexus.example.org",
            "https://nexus.example.org/v1", "https://nexus.example.org?token=bad",
            "https://nexus.example.org#fragment", "https://nexus.example.org:99999",
            "https://nexus.example.org extra",
        )
        for url in invalid:
            with self.subTest(url=url):
                with self.assertRaises(probe.ReadinessFailure):
                    probe.origin_from_config(url)

    def test_public_https_origin_is_normalized(self):
        self.assertEqual(probe.origin_from_config(ORIGIN + "/"), ORIGIN)


if __name__ == "__main__":
    unittest.main()
