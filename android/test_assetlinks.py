"""Digital Asset Links verification fixtures using synthetic certificates."""
from email.message import Message
from io import BytesIO
import json
import unittest

import assetlinks

APP_CERT = ":".join(["AB"] * 32)
OTHER_CERT = ":".join(["CD"] * 32)


def statement(fingerprints, package=assetlinks.PACKAGE_NAME):
    return {
        "relation": [assetlinks.RELATION],
        "target": {
            "namespace": "android_app",
            "package_name": package,
            "sha256_cert_fingerprints": fingerprints,
        },
    }


class Response(BytesIO):
    def __init__(self, payload, status=200, mime="application/json", url=assetlinks.ASSET_LINKS_URL):
        super().__init__(payload)
        self.status = status
        self.url = url
        self.headers = Message()
        self.headers["Content-Type"] = mime

    def geturl(self):
        return self.url


class Opener:
    def __init__(self, response):
        self.response = response

    def open(self, request, timeout):
        assert request.full_url == assetlinks.ASSET_LINKS_URL
        assert timeout > 0
        return self.response


class AssociationTests(unittest.TestCase):
    def check(self, statements, **kwargs):
        return assetlinks.check_public([APP_CERT], Opener(Response(json.dumps(statements).encode(), **kwargs)))

    def test_matches_only_the_studio_certificate(self):
        self.check([statement([APP_CERT.lower()]), statement([OTHER_CERT], "other.app")])

    def test_rejects_missing_wrong_or_additional_studio_certificates(self):
        for statements in ([], [statement([OTHER_CERT])], [statement([APP_CERT, OTHER_CERT])],
                           [statement([APP_CERT], "com.merikation.nexus.studio.debug")],
                           [statement(["not-a-fingerprint"])]):
            with self.subTest(statements=statements), self.assertRaises(ValueError):
                self.check(statements)

    def test_requires_exact_https_response(self):
        for kwargs in ({"status": 302}, {"mime": "text/html"}, {"url": "https://example.invalid/"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.check([statement([APP_CERT])], **kwargs)

    def test_rejects_large_and_malformed_documents(self):
        for raw in (b"x" * (assetlinks.MAX_BYTES + 1), b"{}", b"\xff"):
            with self.subTest(length=len(raw)), self.assertRaises(ValueError):
                assetlinks.check_public([APP_CERT], Opener(Response(raw)))

    def test_matches_relation_as_a_list(self):
        existing = statement([APP_CERT])
        existing["relation"] = assetlinks.RELATION
        with self.assertRaises(ValueError):
            self.check([existing])


if __name__ == "__main__":
    unittest.main()
