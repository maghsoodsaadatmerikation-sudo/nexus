#!/usr/bin/env bash
set -euo pipefail

: "${RUST_IMAGE:?RUST_IMAGE is required}"
: "${GITHUB_SHA:?GITHUB_SHA is required}"
: "${GITHUB_RUN_ID:?GITHUB_RUN_ID is required}"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

RUN_ID="$GITHUB_RUN_ID"
COMMIT_HASH="$GITHUB_SHA"
LOG_FILE="build_verification_${RUN_ID}.log"
RAW_LOG="${LOG_FILE}.tmp"
MANIFEST_FILE="verification-manifest.txt"

cleanup() { rm -f "$RAW_LOG"; }
trap cleanup EXIT

if [[ ! "$RUST_IMAGE" =~ ^rust@sha256:[0-9a-f]{64}$ ]]; then
    echo "[FATAL] Docker image is not digest-pinned to a 64-hex SHA-256 digest."
    exit 1
fi

[[ -f Cargo.toml ]] || { echo "[FATAL] Cargo.toml missing."; exit 1; }
[[ -x scripts/run_gates.sh ]] || { echo "[FATAL] scripts/run_gates.sh missing or not executable."; exit 1; }
[[ -s Cargo.lock ]] || { echo "[FATAL] Cargo.lock missing or empty."; exit 1; }

rm -f "$MANIFEST_FILE"
docker pull "$RUST_IMAGE"
LOCAL_IMAGE_ID="$(docker image inspect "$RUST_IMAGE" --format '{{.Id}}')"
TOOLCHAIN_INFO="$(docker run --rm -e HOME=/tmp/home -e CARGO_HOME=/tmp/cargo "$RUST_IMAGE" sh -c 'rustc --version; cargo --version')"
RUSTC_VERSION="$(printf '%s\n' "$TOOLCHAIN_INFO" | sed -n '1p')"
CARGO_VERSION="$(printf '%s\n' "$TOOLCHAIN_INFO" | sed -n '2p')"
LOCK_HASH_BEFORE="$(sha256sum Cargo.lock | awk '{print $1}')"

if ! {
    echo "[VERIFY] NEXUS Verification Protocol"
    echo "Verified Commit: $COMMIT_HASH"
    echo "Run ID: $RUN_ID"
    echo "Docker Reference: $RUST_IMAGE"
    echo "Docker Local Image ID: $LOCAL_IMAGE_ID"
    echo "Runner: ${RUNNER_OS:-unknown}"
    echo "$RUSTC_VERSION"
    echo "$CARGO_VERSION"
    echo "Cargo.lock SHA-256 (before): $LOCK_HASH_BEFORE"
    echo "[VERIFY] Executing Gates..."
    docker run --rm \
      --user "$(id -u):$(id -g)" \
      -e HOME=/tmp/home \
      -e CARGO_HOME=/tmp/cargo \
      -v "$PROJECT_ROOT:/app" \
      -w /app \
      "$RUST_IMAGE" \
      ./scripts/run_gates.sh
    echo "[VERIFY] Gates completed."
} >"$RAW_LOG" 2>&1; then
    mv "$RAW_LOG" "$LOG_FILE"
    echo "[VERIFY] Gates FAILED."
    exit 1
fi

mv "$RAW_LOG" "$LOG_FILE"
LOCK_HASH_AFTER="$(sha256sum Cargo.lock | awk '{print $1}')"

if [[ "$LOCK_HASH_BEFORE" != "$LOCK_HASH_AFTER" ]]; then
    {
        echo "Cargo.lock SHA-256 (after): $LOCK_HASH_AFTER"
        echo "Cargo.lock invariant: FAIL"
        echo "Status: FAIL"
    } >>"$LOG_FILE"
    exit 1
fi

{
    echo "Cargo.lock SHA-256 (after): $LOCK_HASH_AFTER"
    echo "Cargo.lock invariant: MATCH"
    echo "Verification Mode: locked"
    echo "Status: PASS"
} >>"$LOG_FILE"

LOG_HASH="$(sha256sum "$LOG_FILE" | awk '{print $1}')"
cat >"$MANIFEST_FILE" <<EOF
NEXUS Verification Manifest
===========================

Protocol: NEXUS-Proto-0.1.1
Status: PASS

Verified Commit: $COMMIT_HASH
Run ID: $RUN_ID
Runner: ${RUNNER_OS:-unknown}

Docker Reference: $RUST_IMAGE
Docker Local Image ID: $LOCAL_IMAGE_ID

rustc: $RUSTC_VERSION
cargo: $CARGO_VERSION

Cargo.lock SHA-256: $LOCK_HASH_AFTER
Verification Log SHA-256: $LOG_HASH

Invariant: Cargo.lock unchanged
Verification Mode: locked
EOF

echo "[VERIFY] Manifest generated."
