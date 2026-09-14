#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ROADMAP="docs/V1.2-ROADMAP.md"
CONTRACT="docs/V1.2-OPERATIONAL-ECONOMY.md"

fail() {
  printf 'V1.2 G4 OPERATIONAL ECONOMY: BLOCKED — %s\n' "$1" >&2
  exit 1
}

[[ -f "$ROADMAP" ]] || fail "missing v1.2 roadmap"
[[ -f "$CONTRACT" ]] || fail "missing operational-economy contract"
[[ -f docs/DEPLOYMENT.md ]] || fail "missing deployment contract"

# Production persistence boundary must remain explicit.
grep -F '/data' docs/DEPLOYMENT.md >/dev/null || fail 'durable /data boundary missing'
grep -F 'persistent volume' docs/DEPLOYMENT.md >/dev/null || fail 'persistent volume requirement missing'

# No paid upgrade is an allowed implicit dependency.
grep -F 'No paid resource upgrade is part of this roadmap.' "$ROADMAP" >/dev/null \
  || fail 'roadmap no-paid-upgrade rule missing'
grep -F 'Progression must stop rather than silently incur cost' "$CONTRACT" >/dev/null \
  || fail 'fail-closed cost rule missing'

# Evidence helpers must stay non-authoritative and separable from the production path.
for helper in stage-d-runner stage-d-operator nexus-stage-d-operator nexus-stage-d-restore; do
  grep -F "$helper" "$CONTRACT" >/dev/null || fail "missing helper role: $helper"
done
grep -F 'restart policy is set to `NEVER`' "$CONTRACT" >/dev/null \
  || fail 'restart-disabled helper policy missing'
grep -F 'sleeping mode is enabled' "$CONTRACT" >/dev/null \
  || fail 'sleep-enabled helper policy missing'

# The gate must not overclaim provider capabilities that were not observed.
grep -F 'does **not** claim that the provider configuration has a literal zero-replica value' "$CONTRACT" >/dev/null \
  || fail 'zero-replica limitation not bounded'
grep -F 'does **not** claim a provider-wide billing guarantee' "$CONTRACT" >/dev/null \
  || fail 'billing claim boundary missing'

# Constitutional authority remains unchanged.
grep -F 'A_out <= A_in' "$CONTRACT" >/dev/null || fail 'constitutional invariant missing'

printf '%s\n' 'V1.2 G4 OPERATIONAL ECONOMY: PASS'
printf '%s\n' 'Paid resource upgrade required: NO'
printf '%s\n' 'Authority Expansion: NONE'
