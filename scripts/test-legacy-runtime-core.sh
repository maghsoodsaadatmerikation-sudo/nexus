#!/usr/bin/env bash
# Synthetic regression of the historical runtime's selected pinned source.
# Never replace current checkout sources or claim they equal the old runtime.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fixture="$root/tests/fixtures/legacy-runtime-core"
python3 "$root/scripts/stage-d-core-parity.py" --repo-root "$fixture" \
  --runtime-commit 3c0977f4c7fc9fb5e9a78bdb1eeb581cb3cb4959
stage="$(mktemp -d "${TMPDIR:-/tmp}/nexus-legacy-core.XXXXXXXX")"
trap 'rm -rf "$stage"' EXIT
cp "$root/Cargo.toml" "$root/Cargo.lock" "$root/rust-toolchain.toml" "$stage/"
cp -R "$root/src" "$root/scripts" "$root/tests" "$stage/"
cp -R "$fixture/src/." "$stage/src/"
cp "$fixture/rust-toolchain.toml" "$stage/rust-toolchain.toml"
python3 "$stage/scripts/stage-d-core-parity.py" --repo-root "$stage" \
  --runtime-commit 3c0977f4c7fc9fb5e9a78bdb1eeb581cb3cb4959
cargo build --locked --manifest-path "$stage/Cargo.toml" --bin nexus-private-core-audit
NEXUS_PRIVATE_CORE_AUDIT_BIN="$stage/target/debug/nexus-private-core-audit" \
  python3 "$stage/scripts/test-private-core-audit.py"
