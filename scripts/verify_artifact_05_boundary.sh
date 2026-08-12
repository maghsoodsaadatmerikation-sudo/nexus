#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATEWAY_LIB="$ROOT/artifact-05/src/lib.rs"

[[ -f "$GATEWAY_LIB" ]] || {
    echo "[GATEWAY] gateway library missing"
    exit 1
}

# The HTTP gateway library may only depend on the typed delegate boundary.
# The binary composition root is intentionally allowed to wire the Constitutional
# Core into that delegate; the transport layer itself must never perform these calls.
forbidden='PolicyEngine|Executor|\.authorize\(|\.deny\(|\.execute\(|mutate_policy\('

if grep -nE "$forbidden" "$GATEWAY_LIB"; then
    echo "[GATEWAY] forbidden constitutional operation detected in transport layer"
    exit 1
fi

echo "[GATEWAY] transport authority-boundary check: PASS"
