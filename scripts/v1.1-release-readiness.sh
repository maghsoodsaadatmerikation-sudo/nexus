#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  v1.1-release-readiness.sh <stage-d-evidence-dir> <expected-deployed-commit>

This gate validates an already-produced Stage D evidence pack. It does not
provision infrastructure, perform deployment, create tags, or publish releases.
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
  before.json
  before.sha256
  workspace-id.txt
  deployed-commit.txt
  after-survival.json
  after-restore.json
  result-capture.txt
  result-survival.txt
  result-restore.txt
)
for name in "${required[@]}"; do
  [[ -f "$evidence_dir/$name" ]] || fail "missing Stage D evidence file: $name"
done

recorded_commit="$(tr -d '\r\n' < "$evidence_dir/deployed-commit.txt")"
[[ "$recorded_commit" == "$expected_commit" ]] || fail 'Stage D evidence is not bound to the expected deployed commit'

snapshot_sha="$(sha256sum "$evidence_dir/before.json" | awk '{print $1}')"
recorded_sha="$(tr -d '\r\n' < "$evidence_dir/before.sha256")"
[[ "$snapshot_sha" == "$recorded_sha" ]] || fail 'before.json hash does not match before.sha256'

python3 - "$evidence_dir/before.json" "$evidence_dir/after-survival.json" "$evidence_dir/after-restore.json" <<'PY'
import json, sys
with open(sys.argv[1], encoding='utf-8') as f:
    before = json.load(f)
with open(sys.argv[2], encoding='utf-8') as f:
    survival = json.load(f)
with open(sys.argv[3], encoding='utf-8') as f:
    restored = json.load(f)
if before != survival:
    raise SystemExit('survival snapshot differs from captured snapshot')
if before != restored:
    raise SystemExit('restored snapshot differs from captured snapshot')
workspace_id = before.get('workspace', {}).get('id')
if not isinstance(workspace_id, str) or not workspace_id:
    raise SystemExit('workspace.id missing from captured snapshot')
PY

for phase in capture survival restore; do
  result="$evidence_dir/result-${phase}.txt"
  grep -Fx "Stage D Phase: ${phase}" "$result" >/dev/null || fail "$phase result has wrong phase marker"
  grep -Fx 'Status: PASS' "$result" >/dev/null || fail "$phase result is not PASS"
  grep -Fx "Workspace Snapshot SHA-256: ${snapshot_sha}" "$result" >/dev/null || fail "$phase result hash mismatch"
  grep -Fx 'Token Recorded: NO' "$result" >/dev/null || fail "$phase result does not preserve token hygiene"
  grep -Fx 'Epistemic Claim: operational persistence/recovery only' "$result" >/dev/null || fail "$phase result exceeds the allowed epistemic scope"
  if grep -Eqi 'authorization:[[:space:]]*bearer|NEXUS_API_TOKEN=|Bearer[[:space:]]+[A-Za-z0-9._~+/=-]+' "$result"; then
    fail "$phase result contains credential-like material"
  fi
done

printf '%s\n' \
  'V1.1 RELEASE READINESS: PASS' \
  "Deployed Commit: ${expected_commit}" \
  "Workspace Snapshot SHA-256: ${snapshot_sha}" \
  'Stage D Capture: PASS' \
  'Stage D Survival: PASS' \
  'Stage D Restore: PASS' \
  'Token Recorded: NO' \
  'Authority Expansion: NONE' \
  'Release Action Performed: NO'
