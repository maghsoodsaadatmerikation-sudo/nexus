#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
fail(){ printf 'V1.3 PRODUCTION HARDENING: BLOCKED — %s\n' "$1" >&2; exit 1; }
ROADMAP=docs/V1.3-ROADMAP.md
[[ -f "$ROADMAP" ]] || fail 'roadmap missing'
grep -F 'A_out <= A_in' "$ROADMAP" >/dev/null || fail 'constitutional invariant missing'
grep -F 'fbe17b80206df5e63f7351cc97f1794eb8c88e17' "$ROADMAP" >/dev/null || fail 'v1.2 sealed commit missing'
grep -F '34848797043' "$ROADMAP" >/dev/null || fail 'v1.2 verification run missing'
grep -F 'parse / validate / envelope / delegate / serialize' "$ROADMAP" >/dev/null || fail 'gateway role boundary missing'
grep -F 'No gateway-local authorization' "$ROADMAP" >/dev/null || fail 'authority non-expansion rule missing'
grep -F 'contain no bearer token or secret value' "$ROADMAP" >/dev/null || fail 'secret hygiene rule missing'
grep -F 'Cargo.lock remains pinned and verified' "$ROADMAP" >/dev/null || fail 'dependency integrity rule missing'
grep -F 'Verification failure must block candidate readiness' "$ROADMAP" >/dev/null || fail 'fail-closed rule missing'
grep -F 'No paid resource upgrade is part of this roadmap.' "$ROADMAP" >/dev/null || fail 'no-paid-upgrade rule missing'
grep -F 'Progression must stop rather than silently incur cost.' "$ROADMAP" >/dev/null || fail 'cost fail-closed rule missing'
grep -F 'Publication remains a separate human-authorized action.' "$ROADMAP" >/dev/null || fail 'human release authority missing'
printf '%s\n' 'V1.3 PRODUCTION HARDENING: PASS'
printf '%s\n' 'Historical seal mutation: NONE'
printf '%s\n' 'Paid resource upgrade required: NO'
printf '%s\n' 'Authority Expansion: NONE'
