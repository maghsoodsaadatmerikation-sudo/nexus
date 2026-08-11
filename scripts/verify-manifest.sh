#!/usr/bin/env bash
set -euo pipefail

MANIFEST_FILE="${1:-verification-manifest.txt}"
LOG_FILE="${2:?Usage: verify-manifest.sh <manifest> <log>}"

: "${GITHUB_SHA:?GITHUB_SHA is required}"

[[ -f "$MANIFEST_FILE" ]] || { echo "[SELF-AUDIT] manifest missing"; exit 1; }
[[ -f "$LOG_FILE" ]] || { echo "[SELF-AUDIT] log missing"; exit 1; }
[[ -s Cargo.lock ]] || { echo "[SELF-AUDIT] Cargo.lock missing or empty"; exit 1; }

field() {
    grep -F "$1" "$MANIFEST_FILE" | head -n1 | cut -d: -f2- | sed 's/^ //'
}

STATUS="$(field "Status")"
COMMIT="$(field "Verified Commit")"
RECORDED_LOG_HASH="$(field "Verification Log SHA-256")"
RECORDED_LOCK_HASH="$(field "Cargo.lock SHA-256")"
DOCKER_REF="$(field "Docker Reference")"
INVARIANT="$(field "Invariant")"
MODE="$(field "Verification Mode")"

[[ "$STATUS" == "PASS" ]]
[[ "$COMMIT" == "$GITHUB_SHA" ]]
[[ "$DOCKER_REF" =~ ^rust@sha256:[0-9a-f]{64}$ ]]
[[ "$INVARIANT" == "Cargo.lock unchanged" ]]
[[ "$MODE" == "locked" ]]

grep -q '^NEXUS Verification Manifest$' "$MANIFEST_FILE"
grep -q '^Protocol: NEXUS-Proto-0.1.1$' "$MANIFEST_FILE"
grep -q 'Status: PASS' "$LOG_FILE"
grep -q 'Cargo.lock invariant: MATCH' "$LOG_FILE"
grep -q 'Verification Mode: locked' "$LOG_FILE"

ACTUAL_LOG_HASH="$(sha256sum "$LOG_FILE" | awk '{print $1}')"
ACTUAL_LOCK_HASH="$(sha256sum Cargo.lock | awk '{print $1}')"

[[ "$RECORDED_LOG_HASH" =~ ^[0-9a-f]{64}$ ]]
[[ "$RECORDED_LOCK_HASH" =~ ^[0-9a-f]{64}$ ]]
[[ "$RECORDED_LOG_HASH" == "$ACTUAL_LOG_HASH" ]]
[[ "$RECORDED_LOCK_HASH" == "$ACTUAL_LOCK_HASH" ]]

echo "[SELF-AUDIT] PASS"
