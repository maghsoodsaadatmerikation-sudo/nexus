#!/usr/bin/env python3
"""Prevent a public-site witness from mixing deployed assets with candidate tests.

All operations are read-only and local. No public URL or production service is
contacted; temporary extracted source trees are deleted after the check.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PREPARE = ROOT / "scripts" / "prepare-public-pilot-witness.sh"
EXPECTED_FILES = (
    "web/offline-pilot.html",
    "scripts/test-offline-pilot-browser.py",
    "scripts/observe-public-offline-browser.mjs",
    "scripts/test-decision-report-browser.py",
    "scripts/test-ui-languages-browser.py",
)


def run(args, *, env=None):
    return subprocess.run(
        args, cwd=ROOT, env=env, check=True, capture_output=True, timeout=30
    ).stdout


def main():
    source = PREPARE.read_text(encoding="utf-8")
    match = re.search(r"(?m)^baseline=([0-9a-f]{40})$", source)
    assert match, "public witness must pin an immutable source revision"
    commit = match.group(1)
    with tempfile.TemporaryDirectory(prefix="nexus-published-witness-") as directory:
        env = dict(os.environ, RUNNER_TEMP=directory)
        report = json.loads(run(["bash", str(PREPARE)], env=env).decode().strip())
        assert report["asset_source_commit"] == commit
        assert report["provider_deployment_commit_verified"] is False
        assert report["candidate_promoted_by_this_step"] is False
        assert report["authority"] == "none"
        published = Path(directory) / "nexus-live-pilot"
        for relative in EXPECTED_FILES:
            expected = run(["git", "show", f"{commit}:{relative}"])
            actual = (published / relative).read_bytes()
            assert actual == expected, f"source/witness revision drift: {relative}"
        assert report["expected_published_html_sha256"], "missing source digest"
    print("PASS: public browser test logic and deployed assets use one pinned commit")


if __name__ == "__main__":
    main()
