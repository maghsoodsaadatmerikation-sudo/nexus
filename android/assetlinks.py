#!/usr/bin/env python3
"""Print the public Android association for the owner’s app-signing certificates."""

import argparse
import json
import re


PACKAGE_NAME = "com.merikation.nexus.studio"
FINGERPRINT = re.compile(r"(?:[0-9A-Fa-f]{2}:){31}[0-9A-Fa-f]{2}")


def sha256_fingerprint(value):
    if not FINGERPRINT.fullmatch(value):
        raise argparse.ArgumentTypeError("expected 32 colon-separated hexadecimal SHA-256 bytes")
    return value.upper()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fingerprints", nargs="+", type=sha256_fingerprint)
    arguments = parser.parse_args()
    statement = {
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {
            "namespace": "android_app",
            "package_name": PACKAGE_NAME,
            "sha256_cert_fingerprints": list(dict.fromkeys(arguments.fingerprints)),
        },
    }
    print(json.dumps([statement], indent=2))


if __name__ == "__main__":
    main()
