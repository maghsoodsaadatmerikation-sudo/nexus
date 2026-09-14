#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ROADMAP="docs/V1.3-ROADMAP.md"
RELEASE_V12="docs/RELEASE-v1.2.0.md"
VERIFY_WORKFLOW=".github/workflows/verify.yml"
EXPECTED_V12_COMMIT="fbe17b80206df5e63f7351cc97f1794eb8c88e17"
EXPECTED_V12_RUN="34848797043"

fail() {
  printf 'V1.3 PRODUCTION HARDENING: BLOCKED — %s\n' "$1" >&2
  exit 1
}

for required in \
  "$ROADMAP" \
  "$RELEASE_V12" \
  "$VERIFY_WORKFLOW" \
  artifact-05/Cargo.lock \
  artifact-05/Cargo.toml \
  artifact-05/tests/http_contract.rs \
  artifact-05/tests/product_contract.rs \
  scripts/readonly-verification.sh; do
  [[ -f "$required" ]] || fail "missing ${required}"
done

# G1 — historical seal integrity: verify the actual local tag object, not documentation alone.
grep -F "$EXPECTED_V12_COMMIT" "$RELEASE_V12" >/dev/null || fail 'v1.2 release record commit drift'
grep -F "$EXPECTED_V12_RUN" "$RELEASE_V12" >/dev/null || fail 'v1.2 release record run drift'
git rev-parse -q --verify refs/tags/v1.2.0 >/dev/null || fail 'v1.2.0 tag missing'
[[ "$(git rev-list -n 1 v1.2.0)" == "$EXPECTED_V12_COMMIT" ]] || fail 'v1.2.0 tag moved'
echo 'V1.3 G1 HISTORICAL SEAL INTEGRITY: PASS'

# G2 — gateway authority non-expansion: the gateway contract tests must remain part of
# the locked Artifact 05 test suite. Full execution is performed later by readonly-verification.sh.
grep -F 'http_contract' <(find artifact-05/tests -maxdepth 1 -type f -printf '%f\n') >/dev/null \
  || fail 'HTTP contract test missing'
grep -F 'product_contract' <(find artifact-05/tests -maxdepth 1 -type f -printf '%f\n') >/dev/null \
  || fail 'product contract test missing'
grep -F 'cargo test --locked' scripts/readonly-verification.sh >/dev/null \
  || fail 'locked Artifact 05 test execution missing'
grep -F 'A_out <= A_in' "$ROADMAP" >/dev/null || fail 'constitutional invariant missing'
grep -F 'No gateway-local authorization' "$ROADMAP" >/dev/null || fail 'gateway non-expansion rule missing'
echo 'V1.3 G2 GATEWAY AUTHORITY NON-EXPANSION: PASS'

# G3 — secret/evidence hygiene. Inspect tracked release/evidence manifests and docs;
# source scripts may legitimately contain variable names and redacted test tokens.
while IFS= read -r file; do
  [[ -n "$file" ]] || continue
  if grep -E -i 'authorization:[[:space:]]*Bearer[[:space:]]+[^$<{[:space:]]|NEXUS_API_TOKEN=[^$<{[:space:]]' "$file" >/dev/null 2>&1; then
    fail "possible authentication material in evidence file ${file}"
  fi
done < <(git ls-files 'docs/RELEASE-*.md' '*manifest*.txt')
echo 'V1.3 G3 SECRET AND EVIDENCE HYGIENE: PASS'

# G4 — provenance/dependency integrity.
grep -E '^  RUST_IMAGE: rust@sha256:[0-9a-f]{64}$' "$VERIFY_WORKFLOW" >/dev/null \
  || fail 'verification container is not digest-pinned'
while IFS= read -r use_line; do
  ref="${use_line##*@}"
  [[ "$ref" =~ ^[0-9a-f]{40}$ ]] || fail "GitHub Action is not commit-pinned: ${use_line}"
done < <(grep -E '^[[:space:]]+uses:[[:space:]]+[^#[:space:]]+@' "$VERIFY_WORKFLOW")
grep -F 'cargo build --locked' scripts/readonly-verification.sh >/dev/null || fail 'locked build missing'
grep -F 'cargo test --locked' scripts/readonly-verification.sh >/dev/null || fail 'locked tests missing'
echo 'V1.3 G4 PROVENANCE AND DEPENDENCY INTEGRITY: PASS'

# G5 — failure transparency: scheduled CI must not gain release or repair authority.
for cron in "0 0 * * *" "0 8 * * *" "0 16 * * *"; do
  grep -F -- "- cron: '${cron}'" "$VERIFY_WORKFLOW" >/dev/null || fail "missing schedule ${cron} UTC"
done
if grep -E 'gh[[:space:]]+release[[:space:]]+create|git[[:space:]]+tag|git[[:space:]]+push.*refs/tags' "$VERIFY_WORKFLOW" >/dev/null; then
  fail 'release mutation found in verification workflow'
fi
if grep -E 'workspace-restore\.sh|/v1/workspaces/import' "$VERIFY_WORKFLOW" >/dev/null; then
  fail 'production restore/repair authority found in verification workflow'
fi
echo 'V1.3 G5 FAILURE TRANSPARENCY: PASS'

# G6 — operational economy remains fail-closed and preserves the durable boundary.
grep -F 'No paid resource upgrade is part of this roadmap.' "$ROADMAP" >/dev/null || fail 'no-paid-upgrade rule missing'
grep -F 'Progression must stop rather than silently incur cost.' "$ROADMAP" >/dev/null || fail 'cost fail-closed rule missing'
grep -F '/data' docs/DEPLOYMENT.md >/dev/null || fail 'durable /data boundary missing'
echo 'V1.3 G6 OPERATIONAL ECONOMY: PASS'

printf '%s\n' 'V1.3 PRODUCTION HARDENING: PASS'
printf '%s\n' 'Historical seal mutation: NONE'
printf '%s\n' 'Paid resource upgrade required: NO'
printf '%s\n' 'Authority Expansion: NONE'
