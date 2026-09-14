#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ATTESTATION="evidence/live-deployment-state.json"
EXPECTED_RELEASE_TAG="v1.3.0"
EXPECTED_RELEASE_COMMIT="458260fcadc95b53d5e33fa2fabf806519a8cccd"

fail() {
  printf 'V1.4 DEPLOYMENT TRUTH: BLOCKED — %s\n' "$1" >&2
  exit 1
}

[[ -f "$ATTESTATION" ]] || fail "missing live deployment attestation"
[[ -f docs/V1.4-ROADMAP.md ]] || fail "missing v1.4 roadmap"

python3 - "$ATTESTATION" <<'PY'
import json, re, sys
p=sys.argv[1]
with open(p, encoding='utf-8') as f:
    d=json.load(f)
required={
 'schema','observed_at_utc','provider','environment','service','deployment_id',
 'deployment_status','deployed_commit','source_branch','durable_data_mount',
 'latest_sealed_release','latest_sealed_release_commit','reconciliation',
 'authority_expansion','epistemic_claim','contains_authentication_material'
}
missing=sorted(required-set(d))
if missing:
    raise SystemExit('missing fields: '+','.join(missing))
if d['schema']!='nexus-live-deployment-attestation/v1':
    raise SystemExit('unexpected schema')
if not re.fullmatch(r'[0-9a-f]{40}', d['deployed_commit']):
    raise SystemExit('deployed_commit must be a full lowercase SHA')
if not re.fullmatch(r'[0-9a-f]{40}', d['latest_sealed_release_commit']):
    raise SystemExit('latest_sealed_release_commit must be a full lowercase SHA')
if d['deployment_status']!='SUCCESS':
    raise SystemExit('deployment is not observed SUCCESS')
if d['durable_data_mount']!='/data':
    raise SystemExit('durable data boundary drift')
if d['authority_expansion']!='NONE':
    raise SystemExit('authority expansion detected')
if d['contains_authentication_material'] is not False:
    raise SystemExit('authentication material flag is not false')
if d['reconciliation'] not in {'MATCHES_RELEASE','LIVE_BEHIND_RELEASE','DIVERGED_OR_UNKNOWN'}:
    raise SystemExit('invalid reconciliation classification')
text=open(p, encoding='utf-8').read().lower()
for forbidden in ('bearer ', 'nexus_api_token', 'authorization:', 'ghp_', 'github_pat_'):
    if forbidden in text:
        raise SystemExit('forbidden authentication material marker: '+forbidden)
PY

release_commit="$(git rev-list -n 1 "$EXPECTED_RELEASE_TAG" 2>/dev/null || true)"
[[ "$release_commit" == "$EXPECTED_RELEASE_COMMIT" ]] || fail "sealed v1.3.0 tag drift"

attested_release="$(python3 -c 'import json; print(json.load(open("evidence/live-deployment-state.json"))["latest_sealed_release_commit"])')"
[[ "$attested_release" == "$EXPECTED_RELEASE_COMMIT" ]] || fail "attestation release commit drift"

live_commit="$(python3 -c 'import json; print(json.load(open("evidence/live-deployment-state.json"))["deployed_commit"])')"
recorded_relation="$(python3 -c 'import json; print(json.load(open("evidence/live-deployment-state.json"))["reconciliation"])')"

if [[ "$live_commit" == "$EXPECTED_RELEASE_COMMIT" ]]; then
  derived_relation="MATCHES_RELEASE"
elif git merge-base --is-ancestor "$live_commit" "$EXPECTED_RELEASE_COMMIT" 2>/dev/null; then
  derived_relation="LIVE_BEHIND_RELEASE"
else
  derived_relation="DIVERGED_OR_UNKNOWN"
fi

[[ "$recorded_relation" == "$derived_relation" ]] || fail "recorded reconciliation does not match repository graph"

grep -Fq 'A_out <= A_in' docs/V1.4-ROADMAP.md || fail "constitutional invariant missing"
grep -Fq 'Release publication does not imply production promotion.' docs/V1.4-ROADMAP.md || fail "release/deployment distinction missing"

printf 'V1.4 DEPLOYMENT TRUTH: PASS\n'
printf 'Latest sealed release: %s @ %s\n' "$EXPECTED_RELEASE_TAG" "$EXPECTED_RELEASE_COMMIT"
printf 'Observed live commit: %s\n' "$live_commit"
printf 'Reconciliation: %s\n' "$derived_relation"
printf 'Authority Expansion: NONE\n'
printf 'Production mutation performed: NO\n'
