#!/usr/bin/env bash
set -euo pipefail

echo "[GATE 0] Formatting"
cargo fmt -- --check

echo "[GATE 0] Locked build"
cargo build --locked

echo "[GATE 0] Locked check"
cargo check --locked

echo "[GATE 0] Test compilation"
cargo test --no-run --locked

echo "[GATE 0] Dependency tree"
cargo tree --locked --depth 1

test -f Cargo.lock

echo "[GATE 1] Full test suite"
cargo test --locked

echo "[GATE 2] Type boundary"
cargo test --test type_boundary --locked

# === GATE 3: Evidence Integrity ===
echo "[GATE 3] Lockfile non-empty check"
test -s Cargo.lock

echo "[GATE 3] Lockfile parseability check"
cargo metadata --locked --format-version 1 >/dev/null

echo "[GATES] ALL PASSED"