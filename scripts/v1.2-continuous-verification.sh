#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

workflow=".github/workflows/verify.yml"

fail() {
  printf 'V1.2 G2 CONTINUOUS VERIFICATION: BLOCKED — %s\n' "$1" >&2
  exit 1
}

[[ -f "$workflow" ]] || fail "missing ${workflow}"
[[ -f scripts/readonly-verification.sh ]] || fail "missing read-only verification harness"
[[ -f artifact-05/Cargo.lock ]] || fail "missing Artifact 05 lockfile"

# Source changes on main must trigger deterministic verification.
grep -F 'push:' "$workflow" >/dev/null || fail 'push trigger missing'
grep -F 'branches: [main]' "$workflow" >/dev/null || fail 'main branch push trigger missing'

# Scheduled verification is intentionally fixed at three UTC boundaries.
for cron in "0 0 * * *" "0 8 * * *" "0 16 * * *"; do
  grep -F -- "- cron: '${cron}'" "$workflow" >/dev/null || fail "missing schedule ${cron} UTC"
done

# Verification must remain digest-pinned and must exercise Artifact 05.
grep -E '^  RUST_IMAGE: rust@sha256:[0-9a-f]{64}$' "$workflow" >/dev/null \
  || fail 'Rust image is not digest-pinned'
grep -F 'run: bash scripts/readonly-verification.sh' "$workflow" >/dev/null \
  || fail 'read-only verification harness is not invoked'
grep -F 'Attest Artifact 05 verification bundle' "$workflow" >/dev/null \
  || fail 'Artifact 05 attestation step missing'
grep -F 'artifact-05-verification-bundle.tar.gz' "$workflow" >/dev/null \
  || fail 'Artifact 05 evidence bundle missing'

# A scheduled verification may verify and attest evidence, but it must not publish a release.
if grep -E 'gh release create|git push .*refs/tags|git tag ' "$workflow" >/dev/null; then
  fail 'release mutation found in continuous verification workflow'
fi

echo 'V1.2 G2 CONTINUOUS VERIFICATION: PASS'
echo 'Schedules: 00:00, 08:00, 16:00 UTC'
echo 'Release authority: NONE'
