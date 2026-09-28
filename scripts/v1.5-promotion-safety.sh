#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

EXPECTED_TAG="v1.4.0"
EXPECTED_TARGET="dcf49302e8a8c4c935de3aad0585b19132bad2cd"
EXPECTED_LIVE="480f8771c47e41d4d19b22ed4360bd32c4d2f70a"
EXPECTED_DEPLOYMENT="1f63e3b9-768f-441e-a524-b061394b922e"
ATTESTATION="evidence/live-deployment-state.json"
ROADMAP="docs/V1.5-ROADMAP.md"
GATE="docs/V1.5-RELEASE-GATE.md"
RELEASE_RECORD="docs/RELEASE-v1.4.0.md"
VERIFY_WORKFLOW=".github/workflows/verify.yml"

fail() {
  printf 'V1.5 PROMOTION SAFETY: BLOCKED — %s\n' "$1" >&2
  exit 1
}

for required in "$ATTESTATION" "$ROADMAP" "$GATE" "$RELEASE_RECORD" "$VERIFY_WORKFLOW"; do
  [[ -f "$required" ]] || fail "missing ${required}"
done

# G1/G2 — historical seal and exact promotion target.
git rev-parse -q --verify "refs/tags/${EXPECTED_TAG}" >/dev/null || fail 'v1.4.0 tag missing'
[[ "$(git rev-list -n 1 "$EXPECTED_TAG")" == "$EXPECTED_TARGET" ]] || fail 'v1.4.0 tag drift'
grep -Fq "$EXPECTED_TARGET" "$RELEASE_RECORD" || fail 'v1.4 release record target drift'
grep -Fq '34877496665 — SUCCESS' "$RELEASE_RECORD" || fail 'v1.4 verification evidence drift'

# G3/G5/G6 — provider observation must remain secret-free, durable, and explicit.
python3 - "$ATTESTATION" "$EXPECTED_LIVE" "$EXPECTED_DEPLOYMENT" <<'PY'
import json,re,sys
path, expected_live, expected_deployment = sys.argv[1:]
with open(path, encoding='utf-8') as f:
    d=json.load(f)
if d.get('deployment_status') != 'SUCCESS':
    raise SystemExit('observed production deployment is not SUCCESS')
if d.get('deployed_commit') != expected_live:
    raise SystemExit('rollback-anchor live commit changed without refreshed gate data')
if d.get('deployment_id') != expected_deployment:
    raise SystemExit('rollback-anchor deployment id changed without refreshed gate data')
if d.get('durable_data_mount') != '/data':
    raise SystemExit('durable /data boundary drift')
if d.get('contains_authentication_material') is not False:
    raise SystemExit('authentication material flag is not false')
if d.get('authority_expansion') != 'NONE':
    raise SystemExit('authority expansion detected')
text=open(path,encoding='utf-8').read().lower()
for marker in ('bearer ', 'nexus_api_token', 'authorization:', 'ghp_', 'github_pat_'):
    if marker in text:
        raise SystemExit('forbidden secret marker: '+marker)
if not re.fullmatch(r'[0-9a-f]{40}', d.get('deployed_commit','')):
    raise SystemExit('invalid deployed commit identity')
PY

# G4 — exact identity is mandatory; a moving branch is never sufficient evidence.
grep -Fq 'exact sealed `v1.4.0` commit' "$ROADMAP" || fail 'exact-target rule missing'
grep -Fq 'moving `main`' "$ROADMAP" || fail 'moving-branch rejection missing'
grep -Fq 'promotion must stop rather than approximate' "$ROADMAP" || fail 'fail-closed promotion rule missing'

# Verification CI must not contain provider mutation or release mutation authority.
if grep -E 'railway[[:space:]].*(up|redeploy|deploy)|curl.*railway|gh[[:space:]]+release[[:space:]]+create|git[[:space:]]+push.*refs/tags' "$VERIFY_WORKFLOW" >/dev/null; then
  fail 'production/release mutation found in verification workflow'
fi

# G7 / constitutional and cost boundary.
grep -Fq 'No paid resource upgrade' "$ROADMAP" || fail 'no-paid-upgrade rule missing'
grep -Fq 'No new service or volume' "$ROADMAP" || fail 'no-new-resource rule missing'
grep -Fq 'A_out <= A_in' "$ROADMAP" || fail 'constitutional invariant missing'

printf '%s\n' 'V1.5 PROMOTION SAFETY: PASS'
printf 'Promotion target: %s @ %s\n' "$EXPECTED_TAG" "$EXPECTED_TARGET"
printf 'Rollback anchor live commit: %s\n' "$EXPECTED_LIVE"
printf 'Rollback anchor deployment: %s\n' "$EXPECTED_DEPLOYMENT"
printf '%s\n' 'Durable boundary: /data'
printf '%s\n' 'Promotion executable with connected tooling: NO — exact target binding not established'
printf '%s\n' 'Production promotion performed: NO'
printf '%s\n' 'Paid resource upgrade required: NO'
printf '%s\n' 'Authority Expansion: NONE'
