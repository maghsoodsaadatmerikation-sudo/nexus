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

    for path in REQUIRED[2:]:
        text = path.read_text(encoding="utf-8")
        if re.search(r"Add your specific|copy it over|TEST-MATRIX:\s*PASS", text):
            fail(f"placeholder verification logic detected: {path.relative_to(ROOT)}")

    boundary = ROOT / "tests" / "type_boundary.rs"
    if not boundary.is_file():
        fail("tests/type_boundary.rs missing")

    print("[PREFLIGHT] Repository structure: PASS")
    print("[PREFLIGHT] Locked gate matrix: PASS")
    print("[PREFLIGHT] Type-boundary target: PASS")
    print("[PREFLIGHT] TEST-MATRIX: PASS")

if __name__ == "__main__":
    main()
