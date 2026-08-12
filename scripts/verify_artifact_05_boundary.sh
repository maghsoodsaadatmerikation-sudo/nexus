#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATEWAY="$ROOT/artifact-05/src"

[[ -d "$GATEWAY" ]] || { echo "[GATEWAY] source directory missing"; exit 1; }

# The gateway may only depend on the typed delegate boundary. These symbols would
# create a second authority/execution path if referenced from gateway source.
forbidden='PolicyEngine|Executor|\.authorize\(|\.deny\(|\.execute\(|mutate_policy\('

if grep -RInE "$forbidden" "$GATEWAY"; then
    echo "[GATEWAY] forbidden constitutional operation detected"
    exit 1
fi

echo "[GATEWAY] static authority-boundary check: PASS"
