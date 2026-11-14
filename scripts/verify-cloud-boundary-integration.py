#!/usr/bin/env python3
"""Read-only, fail-closed Git blob provenance check for cloud hardening integration.

This does not grant release authority. SHA-1 is used here only to reproduce
Git's existing blob object identity, not for authentication or signatures.
"""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "integration/cloud-boundary-195-196-manifest.json"
EXPECTED_BASE = "b7855b1a1bb9f3776e8f24b682d124cbe334543e"
EXPECTED = {
    195: {
        "head": "b001aa78f6e8235ecf9dc0fdd282c6dad2397fe9",
        "files": {
            "docs/STUDIO-JSON-BOUNDARY-2026-11-14.md": "1018752b319b14d99168e44633bfce1a477151db",
            "nexus-cloud/studio_model.py": "44fd937737c08b15fa3af265ef4e675de39167a0",
            "nexus-cloud/tests/test_studio_model.py": "7522dbded3fc4935a9789b3a25ae46e4fb42a75f",
        },
    },
    196: {
        "head": "d5895593e56fb56e981828242ec8734c515e1ed8",
        "files": {
            ".github/workflows/pr-verify.yml": "a6a874a76ab06ad38b58161cc56c5064ef90dd5b",
            "docs/CLOUD-HEADER-CARDINALITY-2026-11-14.md": "73857d6fc248202280ba661fe2ab2249a195dcb1",
            "nexus-cloud/main.py": "bfd6bcae1dc38d7f767322113cf30058b421257e",
            "nexus-cloud/tests/test_delegated_header_identity.py": "cbf1da67917f29668fa155e8470a22ddfd117881",
        },
    },
}
EXPECTED_BOUNDARY = {
    "production_mutation": False,
    "release_attestation": False,
    "claim": "source-composition-only",
}


def unique_pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate manifest key")
        obj[key] = value
    return obj


def parse_manifest(raw: bytes):
    if len(raw) > 16384:
        raise ValueError("manifest exceeds limit")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_pairs)


def require_shape(value):
    if not isinstance(value, dict) or set(value) != {
        "schema", "base_commit", "inputs", "boundary"
    }:
        raise ValueError("invalid top-level manifest")
    if value["schema"] != "nexus.integration.cloud-boundary.v1":
        raise ValueError("unrecognized integration schema")
    if value["base_commit"] != EXPECTED_BASE:
        raise ValueError("wrong base commit")
    if value["boundary"] != EXPECTED_BOUNDARY:
        raise ValueError("unexpected authority or production claim")
    inputs = value["inputs"]
    if not isinstance(inputs, list) or len(inputs) != len(EXPECTED):
        raise ValueError("wrong number of sources")
    seen = set()
    all_paths = set()
    for source in inputs:
        if not isinstance(source, dict) or set(source) != {
            "pull_request", "head_commit", "files"
        }:
            raise ValueError("malformed source record")
        pr = source["pull_request"]
        if type(pr) is not int or pr not in EXPECTED or pr in seen:
            raise ValueError("duplicate or unrecognized input PR")
        seen.add(pr)
        reference = EXPECTED[pr]
        if source["head_commit"] != reference["head"]:
            raise ValueError("unpinned source commit")
        files = source["files"]
        if not isinstance(files, list) or len(files) != len(reference["files"]):
            raise ValueError("incorrect source path count")
        observed = {}
        for entry in files:
            if not isinstance(entry, dict) or set(entry) != {"path", "blob_sha"}:
                raise ValueError("invalid file record")
            path = entry["path"]
            if not isinstance(path, str) or path in observed or path in all_paths:
                raise ValueError("duplicate or invalid source path")
            observed[path] = entry["blob_sha"]
            all_paths.add(path)
        if observed != reference["files"]:
            raise ValueError("source blob identities do not match pinned PR")
    if seen != set(EXPECTED):
        raise ValueError("missing source PR")


def git_blob_sha(content: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content)).encode("ascii")
                        + b"\\x00" + content).hexdigest()


def verify_files(root: pathlib.Path):
    for source in EXPECTED.values():
        for rel, expected_sha in source["files"].items():
            path = root / rel
            if not path.is_file() or path.is_symlink():
                raise ValueError(f"missing or symlinked file: {rel}")
            # File sizes are bounded to prevent a pathological snapshot from
            # exhausting verifier memory; these inputs are all small source files.
            if path.stat().st_size > 512 * 1024:
                raise ValueError(f"source exceeds limit: {rel}")
            actual = git_blob_sha(path.read_bytes())
            if actual != expected_sha:
                raise ValueError(f"unexpected Git blob for {rel}")


def self_test():
    base = parse_manifest(MANIFEST.read_bytes())
    require_shape(base)
    changes = (
        lambda o: o["inputs"].append(copy.deepcopy(o["inputs"][0])),
        lambda o: o["inputs"][0]["files"][0].update(blob_sha="0" * 40),
        lambda o: o["inputs"][0].update(head_commit="0" * 40),
        lambda o: o["inputs"][1]["files"][0].update(path="../untrusted"),
        lambda o: o["boundary"].update(production_mutation=True),
        lambda o: o.update(base_commit="0" * 40),
    )
    for mutate in changes:
        test = copy.deepcopy(base)
        mutate(test)
        try:
            require_shape(test)
        except ValueError:
            continue
        raise ValueError("tampered input was not rejected")
    for invalid in (
        b'{"schema":"x","schema":"y"}',
        b'{"nested":{"name":1,"name":2}}',
        b"[" * 20000,
        bytes([255]),
    ):
        try:
            parse_manifest(invalid)
        except (UnicodeError, ValueError):
            continue
        raise ValueError("ambiguous input was not rejected")
    if git_blob_sha(b"abc") != "f2ba8f84ab5c1bce84a7b441cb1959cfc7093b7f":
        raise ValueError("Git blob hash implementation changed")


def main():
    if len(sys.argv) > 2 or (len(sys.argv) == 2 and sys.argv[1] != "--self-test"):
        raise ValueError("unsupported arguments")
    manifest = parse_manifest(MANIFEST.read_bytes())
    require_shape(manifest)
    verify_files(ROOT)
    if len(sys.argv) == 2:
        self_test()
    print("CLOUD SOURCE INTEGRATION: PASS (no production authority)")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, UnicodeError) as exc:
        print("CLOUD SOURCE INTEGRATION: FAIL - " + str(exc), file=sys.stderr)
        sys.exit(1)
