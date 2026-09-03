#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  v1.1-release-readiness.sh <stage-d-evidence-dir> <expected-deployed-commit>

This gate validates an already-produced Stage D evidence pack. It does not
provision infrastructure, perform deployment, create tags, or publish releases.
A PASS requires explicit HTTPS/auth preflight evidence, a recorded real
replacement event before survival verification, an observed destructive absence
before restore, and exact snapshot/commit binding.
EOF
}

fail() {
  printf 'V1.1 RELEASE READINESS: BLOCKED — %s\n' "$1" >&2
  exit 1
}

[[ $# -eq 2 ]] || { usage >&2; exit 2; }
evidence_dir="$1"
expected_commit="$2"

[[ "$expected_commit" =~ ^[0-9a-f]{40}$ ]] || fail 'expected deployed commit must be a full 40-character lowercase SHA'

required=(
  result-preflight.txt
  before.json
  before.sha256
  workspace-id.txt
  deployed-commit.txt
  result-capture.txt
  replacement-event.txt
  after-survival.json
  result-survival.txt
  absence-response.json
  destructive-event.txt
  result-absence.txt
  after-restore.json
  result-restore.txt
)
for name in "${required[@]}"; do
  [[ -f "$evidence_dir/$name" ]] || fail "missing Stage D evidence file: $name"
done

recorded_commit="$(tr -d '\r\n' < "$evidence_dir/deployed-commit.txt")"
[[ "$recorded_commit" == "$expected_commit" ]] || fail 'Stage D evidence is not bound to the expected deployed commit'

snapshot_sha="$(sha256sum "$evidence_dir/before.json" | awk '{print $1}')"
recorded_sha="$(tr -d '\r\n' < "$evidence_dir/before.sha256")"
[[ "$recorded_sha" =~ ^[0-9a-f]{64}$ ]] || fail 'before.sha256 is not a SHA-256 digest'
[[ "$snapshot_sha" == "$recorded_sha" ]] || fail 'before.json hash does not match before.sha256'

preflight="$evidence_dir/result-preflight.txt"
grep -Fx 'Stage D Phase: preflight' "$preflight" >/dev/null || fail 'preflight phase marker missing'
grep -Fx 'Status: PASS' "$preflight" >/dev/null || fail 'preflight is not PASS'
grep -Fx 'Endpoint Scheme: HTTPS' "$preflight" >/dev/null || fail 'HTTPS preflight marker missing'
grep -Fx 'Public Liveness: PASS' "$preflight" >/dev/null || fail 'public liveness was not proven'
grep -Fx 'Missing Bearer Rejected: PASS' "$preflight" >/dev/null || fail 'missing-bearer fail-closed proof missing'
grep -Fx 'Wrong Bearer Rejected: PASS' "$preflight" >/dev/null || fail 'wrong-bearer fail-closed proof missing'
grep -Fx 'Token Recorded: NO' "$preflight" >/dev/null || fail 'preflight token hygiene marker missing'
grep -Fx 'Authority Expansion: NONE' "$preflight" >/dev/null || fail 'preflight authority boundary missing'
grep -Fx 'Epistemic Claim: operational transport boundary only' "$preflight" >/dev/null || fail 'preflight epistemic scope is invalid'

replacement="$evidence_dir/replacement-event.txt"
grep -Fx 'Lifecycle Event: service-replacement' "$replacement" >/dev/null || fail 'replacement lifecycle marker missing'
grep -Fx "Deployed Commit: ${expected_commit}" "$replacement" >/dev/null || fail 'replacement event is not bound to expected commit'
grep -Fx 'Token Recorded: NO' "$replacement" >/dev/null || fail 'replacement event token hygiene marker missing'
grep -Fx 'Authority Expansion: NONE' "$replacement" >/dev/null || fail 'replacement event authority boundary missing'
grep -Fx 'Epistemic Claim: operator/provider lifecycle corroboration only' "$replacement" >/dev/null || fail 'replacement event epistemic scope is invalid'

destructive="$evidence_dir/destructive-event.txt"
grep -Fx 'Lifecycle Event: destructive-backing-state-removal' "$destructive" >/dev/null || fail 'destructive lifecycle marker missing'
grep -Fx 'Observed HTTP Status: 404' "$destructive" >/dev/null || fail 'destructive absence HTTP proof missing'
grep -Fx 'Observed Error: workspace_not_found' "$destructive" >/dev/null || fail 'destructive absence error proof missing'
grep -Fx 'Token Recorded: NO' "$destructive" >/dev/null || fail 'destructive event token hygiene marker missing'
grep -Fx 'Authority Expansion: NONE' "$destructive" >/dev/null || fail 'destructive event authority boundary missing'
grep -Fx 'Epistemic Claim: operator action plus observed workspace absence only' "$destructive" >/dev/null || fail 'destructive event epistemic scope is invalid'

python3 - "$replacement" "$destructive" <<'PY'
import datetime, re, sys

def parse(path, require_commit=False):
    fields = {}
    with open(path, encoding='utf-8') as f:
        for raw in f:
            if ': ' in raw:
                k, v = raw.rstrip('\n').split(': ', 1)
                fields[k] = v
    event_id = fields.get('Event ID', '')
    if not re.fullmatch(r'[A-Za-z0-9._:@/+\=-]{1,200}', event_id):
        raise SystemExit(f'invalid lifecycle Event ID in {path}')
    if re.search(r'authorization|bearer|token|secret|password', event_id, re.I):
        raise SystemExit(f'credential-like lifecycle Event ID in {path}')
    at = fields.get('Event At UTC', '')
    try:
        datetime.datetime.strptime(at, '%Y-%m-%dT%H:%M:%SZ')
    except ValueError:
        raise SystemExit(f'invalid lifecycle UTC timestamp in {path}')
    if require_commit and not re.fullmatch(r'[0-9a-f]{40}', fields.get('Deployed Commit', '')):
        raise SystemExit(f'invalid deployed commit in {path}')

parse(sys.argv[1], require_commit=True)
parse(sys.argv[2])
PY

python3 - "$evidence_dir/before.json" "$evidence_dir/after-survival.json" "$evidence_dir/absence-response.json" "$evidence_dir/after-restore.json" <<'PY'
import json, sys
with open(sys.argv[1], encoding='utf-8') as f:
    before = json.load(f)
with open(sys.argv[2], encoding='utf-8') as f:
    survival = json.load(f)
with open(sys.argv[3], encoding='utf-8') as f:
    absence = json.load(f)
with open(sys.argv[4], encoding='utf-8') as f:
    restored = json.load(f)
if before != survival:
    raise SystemExit('survival snapshot differs from captured snapshot')
if absence != {'error': 'workspace_not_found'}:
    raise SystemExit('destructive absence response is not workspace_not_found')
if before != restored:
    raise SystemExit('restored snapshot differs from captured snapshot')
workspace_id = before.get('workspace', {}).get('id')
if not isinstance(workspace_id, str) or not workspace_id:
    raise SystemExit('workspace.id missing from captured snapshot')
PY

workspace_id="$(python3 - "$evidence_dir/before.json" <<'PY'
import json, sys
with open(sys.argv[1], encoding='utf-8') as f:
    data = json.load(f)
print(data['workspace']['id'])
PY
)"
recorded_workspace="$(tr -d '\r\n' < "$evidence_dir/workspace-id.txt")"
[[ "$recorded_workspace" == "$workspace_id" ]] || fail 'workspace-id.txt does not match captured snapshot'

for phase in capture survival absence restore; do
  result="$evidence_dir/result-${phase}.txt"
  grep -Fx "Stage D Phase: ${phase}" "$result" >/dev/null || fail "$phase result has wrong phase marker"
  grep -Fx 'Status: PASS' "$result" >/dev/null || fail "$phase result is not PASS"
  grep -Fx "Workspace Snapshot SHA-256: ${snapshot_sha}" "$result" >/dev/null || fail "$phase result hash mismatch"
  grep -Fx 'Token Recorded: NO' "$result" >/dev/null || fail "$phase result does not preserve token hygiene"
  grep -Fx 'Authority Expansion: NONE' "$result" >/dev/null || fail "$phase result exceeds authority scope"
  grep -Fx 'Epistemic Claim: operational persistence/recovery only' "$result" >/dev/null || fail "$phase result exceeds allowed epistemic scope"
done

for text_evidence in \
  "$preflight" \
  "$evidence_dir/result-capture.txt" \
  "$replacement" \
  "$evidence_dir/result-survival.txt" \
  "$destructive" \
  "$evidence_dir/result-absence.txt" \
  "$evidence_dir/result-restore.txt"; do
  if grep -Eqi 'authorization:[[:space:]]*bearer[[:space:]]+[A-Za-z0-9._~+/=-]+|NEXUS_API_TOKEN[[:space:]]*=' "$text_evidence"; then
    fail "credential-like material found in $(basename "$text_evidence")"
  fi
done

printf '%s\n' \
  'V1.1 RELEASE READINESS: PASS' \
  "Deployed Commit: ${expected_commit}" \
  "Workspace Snapshot SHA-256: ${snapshot_sha}" \
  'Stage D HTTPS/Auth Preflight: PASS' \
  'Stage D Capture: PASS' \
  'Stage D Replacement Event: RECORDED' \
  'Stage D Survival: PASS' \
  'Stage D Destructive Absence: PASS' \
  'Stage D Restore: PASS' \
  'Token Recorded: NO' \
  'Authority Expansion: NONE' \
  'Release Action Performed: NO'
