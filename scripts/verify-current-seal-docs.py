#!/usr/bin/env python3
"""Fail closed when README's current Seal drifts from sealed release records."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
RELEASES = ROOT / "docs"


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"CURRENT SEAL DOCUMENTATION: BLOCKED — {message}")


def version_tuple(version: str) -> tuple[int, int, int]:
    return tuple(int(part) for part in version.split("."))


readme = README.read_text(encoding="utf-8")
sealed: dict[str, str] = {}
for path in RELEASES.glob("RELEASE-v*.md"):
    match = re.fullmatch(r"RELEASE-v(\d+\.\d+\.\d+)\.md", path.name)
    if not match:
        continue
    text = path.read_text(encoding="utf-8")
    if re.search(r"Status:\s*\*\*SEALED\s*/\s*VERIFIED|\*\*Status:\s*SEALED\s*/\s*VERIFIED", text):
        sealed[match.group(1)] = text

if not sealed:
    fail("no sealed release records found")

latest = max(sealed, key=version_tuple)
heading = re.search(r"^## Current sealed release — v(\d+\.\d+\.\d+)$", readme, re.MULTILINE)
if not heading:
    fail("README current-seal heading missing")
if heading.group(1) != latest:
    fail(f"README says v{heading.group(1)} but latest sealed record is v{latest}")

record = sealed[latest]
tag_match = re.search(r"(?:Release tag:\s*`?|^- Release tag:\s*`?)v(\d+\.\d+\.\d+)`?", record, re.MULTILINE)
if not tag_match or tag_match.group(1) != latest:
    fail("latest release record tag does not match its filename")

candidate_match = re.search(r"Exact (?:release )?candidate:\s*`?([0-9a-f]{40})`?", record)
if not candidate_match:
    fail("latest sealed record lacks an exact 40-character candidate")

release_url = f"https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v{latest}"
if release_url not in readme:
    fail("README release list omits the current sealed release")
if candidate_match.group(1) not in readme:
    fail("README current-seal section omits the exact candidate")

section_match = re.search(
    rf"^## Current sealed release — v{re.escape(latest)}$(.*?)(?=^## )",
    readme,
    re.MULTILINE | re.DOTALL,
)
if not section_match:
    fail("README current-seal section cannot be isolated")
section = section_match.group(1)
for marker in (
    "A_out <= A_in",
    "Authority expansion: NONE",
    "Production mutation: NONE",
    "does not create constitutional authority",
):
    if marker not in section:
        fail(f"README current-seal section missing boundary marker: {marker}")

print("CURRENT SEAL DOCUMENTATION: PASS")
print(f"Current Sealed Release: v{latest}")
print(f"Exact Candidate: {candidate_match.group(1)}")
print("Authority Expansion: NONE")
