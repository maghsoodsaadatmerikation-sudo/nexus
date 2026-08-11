#!/usr/bin/env bash
set -euo pipefail

MANIFEST_FILE="${1:-verification-manifest.txt}"
LOG_FILE="${2:?Usage: verify-manifest.sh <manifest> <log>}"

[[ -f "$MANIFEST_FILE" ]] || exit 1
[[ -f "$LOG_FILE" ]] || exit 1
[[ -s Cargo.lock ]] || exit 1

field() {
    grep -F "$1" "$MANIFEST_FILE" | head -n1 | cut -d: -f2- | sed 's/^ //'
}

STATUS="$(field "Status")"
COMMIT="$(field "Verified Commit")"
RECORDED_LOG_HASH="$(field "Verification Log SHA-256")"
RECORDED_LOCK_HASH="$(field "Cargo.lock SHA-256")"
DOCKER_REF="$(field "Docker Reference")"

[[ "$STATUS" == "PASS" ]]
[[ "$COMMIT" == "$GITHUB_SHA" ]]
[[ "$DOCKER_REF" == rust@sha256:* ]]

ACTUAL_LOG_HASH="$(sha256sum "$LOG_FILE" | awk '{print $1}')"
ACTUAL_LOCK_HASH="$(sha256sum Cargo.lock | awk '{print $1}')"

[[ "$RECORDED_LOG_HASH" == "$ACTUAL_LOG_HASH" ]]
[[ "$RECORDED_LOCK_HASH" == "$ACTUAL_LOCK_HASH" ]]

grep -q "Status: PASS" "$LOG_FILE"
grep -q "Cargo.lock invariant: MATCH" "$LOG_FILE"

echo "[SELF-AUDIT] PASS"