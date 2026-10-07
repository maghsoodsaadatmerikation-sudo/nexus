#!/usr/bin/env python3
"""Read-only verification for Artifact 07 committed truth and optional evidence."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    raise SystemExit(f"ARTIFACT 07 VERIFY: FAIL: {message}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_contract() -> dict:
    controls = json.loads((ROOT / "artifact-07/controls.json").read_text())
    if controls.get("status") != "IMPLEMENTED_UNSEALED":
        fail("committed status must remain implemented and unsealed")
    if controls.get("invariant") != "A_out <= A_in":
        fail("authority invariant is missing")
    if controls.get("claims") != {
        "authority": "NONE",
        "epistemic": "VERIFICATION_ONLY",
        "production_mutation": "NONE",
    }:
        fail("claims exceed the verification boundary")
    expected_ids = [f"A07-{number:02d}" for number in range(1, 7)]
    actual_ids = [control.get("id") for control in controls.get("controls", [])]
    if actual_ids != expected_ids:
        fail("controls must be exactly A07-01..A07-06")

    tests = (ROOT / "artifact-05/tests/http_contract.rs").read_text()
    for control in controls["controls"]:
        if f"fn {control['test']}" not in tests:
            fail(f"missing safety test {control['test']}")

    source = (ROOT / "artifact-05/src/lib.rs").read_text()
    for marker in (
        "max_body_bytes",
        "max_requests_per_window",
        "max_tracked_requests",
        "request_id_replayed",
        "rate_limit_exceeded",
        "request_budget_exhausted",
        "constitutional_delegate_unavailable",
    ):
        if marker not in source:
            fail(f"missing source boundary marker {marker}")

    expected_non_claims = {
        "distributed rate limiting",
        "cross-instance replay defense",
        "durable replay state",
        "identity-specific fairness",
        "denial-of-service immunity",
        "clinical validity",
        "legal authority",
        "organizational approval",
        "production deployment",
        "Seal readiness",
    }
    if set(controls.get("non_claims", [])) != expected_non_claims:
        fail("non-claims changed or are incomplete")
    for lock in (ROOT / "Cargo.lock", ROOT / "artifact-05/Cargo.lock"):
        if not lock.is_file() or lock.stat().st_size == 0:
            fail(f"missing pinned lockfile {lock.relative_to(ROOT)}")
    return controls


def verify_bundle(bundle: Path) -> None:
    if not bundle.is_file():
        fail(f"bundle not found: {bundle}")
    with tempfile.TemporaryDirectory(prefix="nexus-a07-verify-") as temporary:
        target = Path(temporary)
        with tarfile.open(bundle, "r:gz") as archive:
            names = set(archive.getnames())
            required = {"manifest.json", "safety-tests.log", "controls.json"}
            if not required.issubset(names):
                fail("bundle is missing required evidence")
            for member in archive.getmembers():
                resolved = (target / member.name).resolve()
                if target.resolve() not in resolved.parents and resolved != target.resolve():
                    fail("unsafe archive path")
            archive.extractall(target)

        manifest = json.loads((target / "manifest.json").read_text())
        if manifest.get("status") != "PASS":
            fail("manifest status is not PASS")
        if not re.fullmatch(r"[0-9a-f]{40}", manifest.get("verified_commit", "")):
            fail("verified commit is not exact")
        required_manifest = {
            "authority_claim": "NONE",
            "epistemic_claim": "VERIFICATION_ONLY",
            "production_mutation": "NONE",
            "sealed": False,
            "invariant": "A_out <= A_in",
            "bootstrap_verify_separation": True,
        }
        for key, value in required_manifest.items():
            if manifest.get(key) != value:
                fail(f"invalid manifest field {key}")
        expected_locks = {
            "Cargo.lock": sha256(ROOT / "Cargo.lock"),
            "artifact-05/Cargo.lock": sha256(ROOT / "artifact-05/Cargo.lock"),
        }
        if manifest.get("cargo_locks") != expected_locks:
            fail("bundle lock digests differ from committed locks")
        for name in ("safety-tests.log", "controls.json"):
            if manifest.get("files", {}).get(name) != sha256(target / name):
                fail(f"digest mismatch for {name}")
        if "6 passed" not in (target / "safety-tests.log").read_text():
            fail("six Artifact 07 PASS results are absent")
        if json.loads((target / "controls.json").read_text()) != json.loads(
            (ROOT / "artifact-07/controls.json").read_text()
        ):
            fail("bundle controls differ from committed truth")


def main() -> None:
    if len(sys.argv) > 2:
        fail("usage: verify-artifact-07.py [evidence-bundle]")
    verify_contract()
    if len(sys.argv) == 2:
        verify_bundle(Path(sys.argv[1]).resolve())
    print("ARTIFACT 07 READ-ONLY VERIFY: PASS")


if __name__ == "__main__":
    main()
