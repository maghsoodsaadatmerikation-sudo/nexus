#!/usr/bin/env python3
"""Local negative tests for non-mutating public HTTPS preview observer."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).with_name("observe-portable-pwa-preview.py")
spec = importlib.util.spec_from_file_location("public_pwa_observer", SCRIPT)
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)


class PublicPreviewObserverTests(unittest.TestCase):
    def test_exact_html_is_accepted_with_correct_mime(self):
        actual = b"<!doctype html><title>NEXUS</title>"
        report = observer.compare("nexus/index.html", 200, "text/html; charset=utf-8",
                                  actual, actual)
        self.assertEqual(report["status"], "PASS")

    def test_wrong_html_bytes_are_rejected(self):
        self.assertEqual(observer.compare("nexus/index.html", 200, "text/html",
                                          b"bad", b"expected")["status"], "FAIL_CLOSED")

    def test_redirect_or_wrong_http_status_fail_closed(self):
        for code in (301, 302, 307, 401, 404, 500):
            self.assertEqual(observer.compare("nexus/index.html", code, "text/html",
                                              b"same", b"same")["status"], "FAIL_CLOSED")
        self.assertEqual(observer.compare("nexus/index.html", 200, "text/html",
                                          b"same", b"same", redirected=True)["status"],
                         "FAIL_CLOSED")

    def test_media_type_confusion_fails_closed(self):
        self.assertFalse(observer.mime_allowed("nexus/index.html", "application/json"))
        self.assertFalse(observer.mime_allowed("nexus/service-worker.js", "text/html"))
        self.assertFalse(observer.mime_allowed("nexus/PWA-KIT.json", "text/plain"))
        self.assertFalse(observer.mime_allowed("nexus/icons/nexus-192.png", "text/plain"))
        self.assertTrue(observer.mime_allowed("nexus/START-HERE.txt",
                                              "text/plain; charset=utf-8"))

    def test_no_redirect_handler_refuses_all_location_changes(self):
        from urllib.request import Request
        original = Request(observer.ORIGIN + "nexus/index.html",
                           headers={"Authorization": "Bearer SYNTHETIC"})
        for code in (301, 302, 303, 307, 308):
            self.assertIsNone(observer.NoRedirect().redirect_request(
                original, None, code, "redirection", {},
                "https://untrusted.example/collect"))

    def test_oversized_response_is_not_accepted(self):
        body = b"z" * (observer.MAX_RESPONSE + 1)
        self.assertEqual(observer.compare("nexus/index.html", 200, "text/html",
                                          body, body)["status"], "FAIL_CLOSED")

    def test_only_public_frozen_host_and_exact_deployed_commit(self):
        self.assertEqual(observer.ORIGIN,
                         "https://nexus-merikation-pwa-preview.onrender.com/")
        self.assertEqual(observer.RELEASE_SHA,
                         "4b4f32ab54fa6ce8bf4a7f0c1a428c6237307d42")
        self.assertEqual(len(observer.BUILDER.expected(observer.RELEASE_SHA)), 8)


if __name__ == "__main__":
    unittest.main()
