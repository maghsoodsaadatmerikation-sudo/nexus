#!/usr/bin/env python3
"""Read-only verification for Artifact 06 committed truth and optional evidence."""

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
    raise SystemExit(f"ARTIFACT 06 VERIFY: FAIL: {message}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_contract() -> dict:
    catalog_path = ROOT / "artifact-06/scenarios.json"
    catalog = json.loads(catalog_path.read_text())
    controls = catalog.get("canonical_controls", [])
    expected = [f"CT-{number:03d}" for number in range(1, 21)]
    actual = [control.get("id") for control in controls]
    if actual != expected:
        fail("canonical controls must be exactly CT-001..020 in order")
    if len({control.get("test") for control in controls}) != 20:
        fail("each canonical control must map to one distinct test")

    core_tests = (ROOT / "tests/constitutional_tests.rs").read_text()
    for control in controls:
        if f"fn {control['test']}" not in core_tests:
            fail(f"missing canonical test {control['test']}")

    http_tests = (ROOT / "artifact-05/tests/http_contract.rs").read_text()
    probes = catalog.get("transport_probes", [])
    if not probes:
        fail("transport probes are required")
    for probe in probes:
        if f"fn {probe['test']}" not in http_tests:
            fail(f"missing transport probe {probe['test']}")

    claims = catalog.get("claims", {})
    if claims != {
        "authority": "NONE",
        "epistemic": "VERIFICATION_ONLY",
        "production_mutation": "NONE",
    }:
        fail("claims must remain non-authoritative and non-mutating")
    if catalog.get("invariant") != "A_out <= A_in":
        fail("authority invariant is missing")

    required_non_claims = {
        "clinical validity",
        "legal authority",
        "organizational approval",
        "replay protection",
        "rate limiting",
        "payload size enforcement",
        "public deployment readiness",
        "Seal readiness",
    }
    if set(catalog.get("non_claims", [])) != required_non_claims:
        fail("non-claims changed or are incomplete")
    for lock in (ROOT / "Cargo.lock", ROOT / "artifact-05/Cargo.lock"):
        if not lock.is_file() or lock.stat().st_size == 0:
            fail(f"missing pinned lockfile {lock.relative_to(ROOT)}")
    return catalog


def verify_bundle(bundle: Path) -> None:
    if not bundle.is_file():
        fail(f"bundle not found: {bundle}")
    with tempfile.TemporaryDirectory(prefix="nexus-a06-verify-") as temporary:
        target = Path(temporary)
        with tarfile.open(bundle, "r:gz") as archive:
            names = set(archive.getnames())
            required = {"manifest.json", "core-tests.log", "gateway-tests.log", "scenarios.json"}
            if not required.issubset(names):
                fail("bundle is missing required evidence files")
            for member in archive.getmembers():
                resolved = (target / member.name).resolve()
                if target.resolve() not in resolved.parents and resolved != target.resolve():
                    fail("unsafe archive path")
            archive.extractall(target)

        manifest = json.loads((target / "manifest.json").read_text())
        if manifest.get("status") != "PASS":
            fail("manifest status is not PASS")
        if not re.fullmatch(r"[0-9a-f]{40}", manifest.get("verified_commit", "")):
            fail("verified commit is not an exact SHA")
        if manifest.get("authority_claim") != "NONE":
            fail("bundle makes an authority claim")
        if manifest.get("epistemic_claim") != "VERIFICATION_ONLY":
            fail("bundle exceeds the verification boundary")
        if manifest.get("production_mutation") != "NONE":
            fail("bundle claims production mutation")
        if manifest.get("sealed") is not False:
            fail("Lab evidence must not claim a Seal")
        if manifest.get("invariant") != "A_out <= A_in":
            fail("bundle authority invariant is missing")
        if manifest.get("bootstrap_verify_separation") is not True:
            fail("bundle does not preserve Bootstrap/Verify separation")

        expected_locks = {
            "Cargo.lock": sha256(ROOT / "Cargo.lock"),
            "artifact-05/Cargo.lock": sha256(ROOT / "artifact-05/Cargo.lock"),
        }
        if manifest.get("cargo_locks") != expected_locks:
            fail("bundle lockfile digests differ from committed pinned locks")

        files = manifest.get("files", {})
        for name in ("core-tests.log", "gateway-tests.log", "scenarios.json"):
            if files.get(name) != sha256(target / name):
                fail(f"digest mismatch for {name}")
        if "20 passed" not in (target / "core-tests.log").read_text():
            fail("canonical CT-001..020 PASS evidence is absent")
        if "test result: ok" not in (target / "gateway-tests.log").read_text():
            fail("Gateway PASS evidence is absent")
        if json.loads((target / "scenarios.json").read_text()) != json.loads(
            (ROOT / "artifact-06/scenarios.json").read_text()
        ):
            fail("bundle scenario catalog differs from committed truth")


def main() -> None:
    if len(sys.argv) > 2:
        fail("usage: verify-artifact-06.py [evidence-bundle]")
    verify_contract()
    if len(sys.argv) == 2:
        verify_bundle(Path(sys.argv[1]).resolve())
    print("ARTIFACT 06 READ-ONLY VERIFY: PASS")


if __name__ == "__main__":
    main()
