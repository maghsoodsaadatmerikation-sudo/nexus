#!/usr/bin/env bash
set -euo pipefail

EXPECTED_V11_COMMIT="480f8771c47e41d4d19b22ed4360bd32c4d2f70a"
EXPECTED_V11_RUN="34824938788"
EXPECTED_WORKSPACE_SHA="71271177cadc1dd67afdf0ddbc913c89c54b326df66bdb2f1dd803da94107d7b"
RELEASE_RECORD="docs/RELEASE-v1.1.0.md"

fail() {
  printf 'V1.2 BOUNDARY INTEGRITY: BLOCKED — %s\n' "$1" >&2
  exit 1
}

[[ -f "$RELEASE_RECORD" ]] || fail "missing v1.1.0 release record"

grep -Fq "$EXPECTED_V11_COMMIT" "$RELEASE_RECORD" || fail "sealed commit drift"
grep -Fq "$EXPECTED_V11_RUN" "$RELEASE_RECORD" || fail "verification run drift"
grep -Fq "$EXPECTED_WORKSPACE_SHA" "$RELEASE_RECORD" || fail "workspace evidence hash drift"
grep -Fq 'A_out <= A_in' "$RELEASE_RECORD" || fail "constitutional invariant missing"
grep -Fq 'v1.1.0' "$RELEASE_RECORD" || fail "release identity missing"

if git rev-parse -q --verify refs/tags/v1.1.0 >/dev/null 2>&1; then
  TAG_COMMIT="$(git rev-list -n 1 v1.1.0)"
  [[ "$TAG_COMMIT" == "$EXPECTED_V11_COMMIT" ]] || fail "v1.1.0 tag moved from sealed commit"
else
  fail "v1.1.0 tag missing"
fi

printf '%s\n' 'V1.2 BOUNDARY INTEGRITY: PASS'
printf 'v1.1.0 commit: %s\n' "$EXPECTED_V11_COMMIT"
printf 'verification run: %s\n' "$EXPECTED_V11_RUN"
printf 'workspace SHA-256: %s\n' "$EXPECTED_WORKSPACE_SHA"
printf '%s\n' 'Authority Expansion: NONE'
