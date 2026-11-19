#!/usr/bin/env python3
"""Generate or check the public association for Studio’s Android app."""

import argparse
import json
import re
import sys
from urllib.error import URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


PACKAGE_NAME = "com.merikation.nexus.studio"
ASSET_LINKS_URL = "https://nexus-studio-merikation.onrender.com/.well-known/assetlinks.json"
RELATION = "delegate_permission/common.handle_all_urls"
MAX_BYTES = 65536
FINGERPRINT = re.compile(r"(?:[0-9A-Fa-f]{2}:){31}[0-9A-Fa-f]{2}")


def sha256_fingerprint(value):
    if not FINGERPRINT.fullmatch(value):
        raise argparse.ArgumentTypeError("expected 32 colon-separated hexadecimal SHA-256 bytes")
    return value.upper()


def public_fingerprints(statements):
    if not isinstance(statements, list):
        raise ValueError("expected a JSON array of statements")
    fingerprints = set()
    for statement in statements:
        if not isinstance(statement, dict):
            raise ValueError("invalid association statement")
        target = statement.get("target")
        if not isinstance(target, dict) or target.get("package_name") != PACKAGE_NAME:
            continue
        relation = statement.get("relation")
        if target.get("namespace") != "android_app" or not isinstance(relation, list) or RELATION not in relation:
            raise ValueError("Studio statement must delegate URL handling to the Android app")
        values = target.get("sha256_cert_fingerprints")
        if not isinstance(values, list) or not values:
            raise ValueError("Studio statement is missing certificates")
        for value in values:
            if not isinstance(value, str) or not FINGERPRINT.fullmatch(value):
                raise ValueError("Studio statement contains an invalid certificate fingerprint")
            fingerprints.add(value.upper())
    return fingerprints


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def check_public(fingerprints, opener=None):
    request = Request(ASSET_LINKS_URL, headers={"Accept": "application/json"})
    opener = opener or build_opener(NoRedirect())
    with opener.open(request, timeout=12) as response:
        if response.status != 200 or response.geturl() != ASSET_LINKS_URL:
            raise ValueError("association must return HTTP 200 at the exact public URL")
        if response.headers.get_content_type() != "application/json":
            raise ValueError("association must serve application/json")
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("association document exceeds the size limit")
    published = public_fingerprints(json.loads(raw.decode("utf-8")))
    if published != set(fingerprints):
        raise ValueError("public Studio certificates differ from the approved fingerprints")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-public", action="store_true", help="verify the live HTTPS association")
    parser.add_argument("fingerprints", nargs="+", type=sha256_fingerprint)
    arguments = parser.parse_args()
    if arguments.check_public:
        try:
            check_public(arguments.fingerprints)
        except (URLError, OSError, ValueError) as error:
            print(f"Android association blocked: {error}", file=sys.stderr)
            return 1
        print(f"Android association verified for {PACKAGE_NAME}")
        return 0

    statement = {
        "relation": [RELATION],
        "target": {
            "namespace": "android_app",
            "package_name": PACKAGE_NAME,
            "sha256_cert_fingerprints": list(dict.fromkeys(arguments.fingerprints)),
        },
    }
    print(json.dumps([statement], indent=2))


if __name__ == "__main__":
    sys.exit(main())
