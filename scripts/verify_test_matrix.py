#!/usr/bin/env python3
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
REQUIRED = [
    ROOT / "Cargo.toml",
    ROOT / "Cargo.lock",
    ROOT / "scripts" / "run_gates.sh",
    ROOT / "scripts" / "verify-docker.sh",
    ROOT / "scripts" / "verify-manifest.sh",
    ROOT / "scripts" / "bootstrap-docker.sh",
    ROOT / "scripts" / "stage-d-evidence.sh",
    ROOT / "scripts" / "v1.1-release-readiness.sh",
    ROOT / "scripts" / "v1.1-release-candidate.sh",
    ROOT / "scripts" / "test-stage-d-readiness.sh",
    ROOT / "docs" / "STAGE-D-EVIDENCE.md",
    ROOT / "docs" / "RELEASE-READINESS-v1.1.md",
    ROOT / "docs" / "RELEASE-CANDIDATE-v1.1.md",
]

def fail(message: str) -> None:
    print(f"[PREFLIGHT] FAIL: {message}")
    raise SystemExit(1)

def main() -> None:
    print("[PREFLIGHT] Verifying repository structure and test boundary...")
    for path in REQUIRED:
        if not path.is_file():
            fail(f"required file missing: {path.relative_to(ROOT)}")

    gates = (ROOT / "scripts" / "run_gates.sh").read_text(encoding="utf-8")
    required_markers = [
        "cargo build --locked",
        "cargo check --locked",
        "cargo test --locked",
        "cargo test --test type_boundary --locked",
        "cargo metadata --locked --format-version 1",
    ]
    for marker in required_markers:
        if marker not in gates:
            fail(f"required gate command missing: {marker}")

    for path in REQUIRED[2:6]:
        text = path.read_text(encoding="utf-8")
        if re.search(r"Add your specific|copy it over|TEST-MATRIX:\s*PASS", text):
            fail(f"placeholder verification logic detected: {path.relative_to(ROOT)}")

    stage_d = (ROOT / "scripts" / "stage-d-evidence.sh").read_text(encoding="utf-8")
    for marker in [
        "preflight)",
        "capture)",
        "record-replacement)",
        "verify-survival)",
        "verify-absence)",
        "restore-verify)",
        "Token Recorded: NO",
        "Authority Expansion: NONE",
        "NEXUS_DEPLOYED_COMMIT",
        "NEXUS_REPLACEMENT_EVENT_ID",
        "NEXUS_DESTRUCTIVE_EVENT_ID",
        "replacement-event.txt",
        "destructive-event.txt",
        "absence-response.json",
        "workspace-backup.sh",
        "workspace-restore.sh",
    ]:
        if marker not in stage_d:
            fail(f"Stage D evidence harness marker missing: {marker}")
    if "NEXUS_API_TOKEN" not in stage_d:
        fail("Stage D harness must require authenticated access for network phases")
    token_record_lines = [
        line.strip()
        for line in stage_d.splitlines()
        if "Token Recorded:" in line and not line.lstrip().startswith("#")
    ]
    if not token_record_lines or any(line != "Token Recorded: NO" for line in token_record_lines):
        fail("Stage D harness must record only explicit no-token markers")

    stage_d_doc = (ROOT / "docs" / "STAGE-D-EVIDENCE.md").read_text(encoding="utf-8")
    for marker in [
        "A_out <= A_in",
        "real service/container replacement",
        "verify-absence",
        "must not be sealed",
        "deployed-commit.txt",
        "replacement-event.txt",
        "destructive-event.txt",
        "v1.1-release-readiness.sh",
    ]:
        if marker not in stage_d_doc:
            fail(f"Stage D evidence protocol marker missing: {marker}")

    readiness = (ROOT / "scripts" / "v1.1-release-readiness.sh").read_text(encoding="utf-8")
    for marker in [
        "V1.1 RELEASE READINESS: BLOCKED",
        "V1.1 RELEASE READINESS: PASS",
        "Release Action Performed: NO",
        "deployed-commit.txt",
        "replacement-event.txt",
        "after-survival.json",
        "absence-response.json",
        "destructive-event.txt",
        "after-restore.json",
        "Stage D Destructive Absence: PASS",
    ]:
        if marker not in readiness:
            fail(f"release readiness marker missing: {marker}")
    for marker in [': "${NEXUS_API_TOKEN:', 'authorization: Bearer ${NEXUS_API_TOKEN}']:
        if marker in readiness:
            fail("release readiness validation must not require bearer-token access")

    readiness_doc = (ROOT / "docs" / "RELEASE-READINESS-v1.1.md").read_text(encoding="utf-8")
    readiness_doc_folded = readiness_doc.casefold()
    for marker in ["a_out <= a_in", "fail-closed", "does not create a tag", "destructive absence"]:
        if marker not in readiness_doc_folded:
            fail(f"release readiness documentation marker missing: {marker}")

    candidate = (ROOT / "scripts" / "v1.1-release-candidate.sh").read_text(encoding="utf-8")
    for marker in [
        "V1.1 RELEASE CANDIDATE: BLOCKED",
        "V1.1 RELEASE CANDIDATE: READY",
        "READY FOR HUMAN RELEASE DECISION",
        "Verification Run Independently Checked: NO",
        "Stage D Destructive Absence: PASS",
        "Release Action Performed: NO",
        "Tag Created: NO",
        "GitHub Release Published: NO",
        "v1.1-release-readiness.sh",
    ]:
        if marker not in candidate:
            fail(f"release candidate marker missing: {marker}")
    if "NEXUS_API_TOKEN" in candidate or "authorization: Bearer" in candidate:
        fail("release candidate packaging must not require bearer-token access")

    candidate_doc = (ROOT / "docs" / "RELEASE-CANDIDATE-v1.1.md").read_text(encoding="utf-8").casefold()
    for marker in ["a_out <= a_in", "fail-closed", "human release boundary", "does not create a tag", "independently checked"]:
        if marker not in candidate_doc:
            fail(f"release candidate documentation marker missing: {marker}")

    lifecycle_test = (ROOT / "scripts" / "test-stage-d-readiness.sh").read_text(encoding="utf-8")
    for marker in [
        "STAGE D LIFECYCLE READINESS TESTS: PASS",
        "missing replacement evidence",
        "invalid destructive absence evidence",
        "different deployed commit",
    ]:
        if marker not in lifecycle_test:
            fail(f"Stage D lifecycle test marker missing: {marker}")

    boundary = ROOT / "tests" / "type_boundary.rs"
    if not boundary.is_file():
        fail("tests/type_boundary.rs missing")

    print("[PREFLIGHT] Repository structure: PASS")
    print("[PREFLIGHT] Locked gate matrix: PASS")
    print("[PREFLIGHT] Stage D lifecycle evidence boundary: PASS")
    print("[PREFLIGHT] Stage E release-readiness boundary: PASS")
    print("[PREFLIGHT] Stage F release-candidate boundary: PASS")
    print("[PREFLIGHT] Type-boundary target: PASS")
    print("[PREFLIGHT] TEST-MATRIX: PASS")

if __name__ == "__main__":
    main()
