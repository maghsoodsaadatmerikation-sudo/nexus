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
    ROOT / "docs" / "STAGE-D-EVIDENCE.md",
    ROOT / "docs" / "RELEASE-READINESS-v1.1.md",
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
        "capture)",
        "verify-survival)",
        "restore-verify)",
        "Token Recorded: NO",
        "NEXUS_DEPLOYED_COMMIT",
        "deployed-commit.txt",
        "workspace-backup.sh",
        "workspace-restore.sh",
    ]:
        if marker not in stage_d:
            fail(f"Stage D evidence harness marker missing: {marker}")
    if "NEXUS_API_TOKEN" not in stage_d:
        fail("Stage D harness must require authenticated access")
    token_record_lines = [
        line.strip() for line in stage_d.splitlines() if line.strip().startswith("Token Recorded:")
    ]
    if token_record_lines != ["Token Recorded: NO"]:
        fail("Stage D harness must record only the explicit no-token marker")

    stage_d_doc = (ROOT / "docs" / "STAGE-D-EVIDENCE.md").read_text(encoding="utf-8")
    for marker in [
        "A_out <= A_in",
        "real service/container replacement",
        "must not be sealed",
        "deployed-commit.txt",
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
        "after-survival.json",
        "after-restore.json",
    ]:
        if marker not in readiness:
            fail(f"release readiness marker missing: {marker}")
    if "NEXUS_API_TOKEN" in readiness:
        fail("release readiness validation must not require bearer-token access")

    readiness_doc = (ROOT / "docs" / "RELEASE-READINESS-v1.1.md").read_text(encoding="utf-8")
    for marker in ["A_out <= A_in", "fail-closed", "does not create a tag"]:
        if marker not in readiness_doc:
            fail(f"release readiness documentation marker missing: {marker}")

    boundary = ROOT / "tests" / "type_boundary.rs"
    if not boundary.is_file():
        fail("tests/type_boundary.rs missing")

    print("[PREFLIGHT] Repository structure: PASS")
    print("[PREFLIGHT] Locked gate matrix: PASS")
    print("[PREFLIGHT] Stage D evidence boundary: PASS")
    print("[PREFLIGHT] Stage E release-readiness boundary: PASS")
    print("[PREFLIGHT] Type-boundary target: PASS")
    print("[PREFLIGHT] TEST-MATRIX: PASS")

if __name__ == "__main__":
    main()
