#!/usr/bin/env python3
"""Fail closed when pull-request code can run with evidence publishing privileges."""

from pathlib import Path
import re


WORKFLOWS = Path(".github/workflows")
PR_WORKFLOWS = ("pr-verify.yml", "cloud-adapter.yml")
PRIVILEGED = (
    "v2.3-revocation-freshness.yml",
    "v2.4-gateway-authority-confusion.yml",
    "v2.5-transport-authentication.yml",
)


def event_block(source: str) -> str:
    match = re.search(r"(?m)^on:\s*\n(.*?)(?=^[A-Za-z][\w-]*:|\Z)", source, re.S | re.M)
    if match is None:
        raise ValueError("missing top-level workflow events")
    return match.group(1)


def check() -> None:
    for path in WORKFLOWS.glob("*.yml"):
        source = path.read_text()
        events = event_block(source)
        if re.search(r"(?m)^  pull_request(?:_target)?:", events):
            assert "pull_request_target:" not in events, path.name
            assert not re.search(
                r"(?m)^\s+(?:id-token|attestations|contents): write\s*$", source
            ), path.name

    for name in PR_WORKFLOWS:
        source = (WORKFLOWS / name).read_text()
        events = event_block(source)
        assert re.search(r"(?m)^  pull_request:\s*$", events), name
        assert re.search(r"(?m)^  contents: read\s*$", source), name
        assert not re.search(r"(?m)^\s+(?:id-token|attestations): write\s*$", source), name
        assert "pull_request_target:" not in events, name

    for name in PRIVILEGED:
        source = (WORKFLOWS / name).read_text()
        events = event_block(source)
        assert re.search(r"(?m)^  push:\s*$", events), name
        assert re.search(r"(?m)^    branches: \[main\]\s*$", events), name
        assert not re.search(r"(?m)^  pull_request(?:_target)?:", events), name
        assert "id-token: write" in source and "attestations: write" in source, name


if __name__ == "__main__":
    check()
    print("WORKFLOW AUTHORITY BOUNDARY: PASS")
