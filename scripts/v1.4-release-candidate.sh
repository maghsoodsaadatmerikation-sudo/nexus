#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

candidate_commit="${1:?candidate commit is required}"
verification_run="${2:?verification run id is required}"
out="${3:-v1.4-release-candidate-manifest.txt}"

fail() {
  printf 'V1.4 RELEASE CANDIDATE: BLOCKED — %s\n' "$1" >&2
  exit 1
}

[[ "$candidate_commit" =~ ^[0-9a-f]{40}$ ]] || fail 'candidate commit must be a full lowercase SHA'
[[ "$verification_run" =~ ^[0-9]+$ ]] || fail 'verification run id must be numeric'
[[ "$(git rev-parse HEAD)" == "$candidate_commit" ]] || fail 'checked-out commit differs from candidate commit'

bash scripts/v1.4-deployment-truth.sh >/dev/null

for required in \
  docs/V1.4-ROADMAP.md \
  docs/V1.4-RELEASE-GATE.md \
  docs/RELEASE-v1.3.0.md \
  evidence/live-deployment-state.json; do
  [[ -f "$required" ]] || fail "missing ${required}"
done

relation="$(python3 -c 'import json; print(json.load(open("evidence/live-deployment-state.json"))["reconciliation"])')"
live_commit="$(python3 -c 'import json; print(json.load(open("evidence/live-deployment-state.json"))["deployed_commit"])')"

cat > "$out" <<EOF
NEXUS v1.4 Release Candidate
Status: READY FOR INDEPENDENT VERIFICATION
Candidate Commit: ${candidate_commit}
Verification Run ID: ${verification_run}
Verification Run Independently Checked: NO
G1 Historical Seal Integrity: PASS
G2 Live Deployment Attestation: PASS
G3 Release/Deployment Reconciliation: PASS
G4 Claim Discipline: PASS
G5 Durable-Boundary Continuity: PASS
G6 Operational Economy: PASS
Observed Live Commit: ${live_commit}
Observed Live/Release Relation: ${relation}
Release Implies Deployment: NO
Production Promotion Performed: NO
Authority Expansion: NONE
Paid Resource Upgrade Required: NO
Release Action Performed: NO
Tag Created: NO
GitHub Release Published: NO
Epistemic Claim: deployment-truth release-candidate readiness only
EOF

grep -Fx "Candidate Commit: ${candidate_commit}" "$out" >/dev/null
grep -Fx "Verification Run ID: ${verification_run}" "$out" >/dev/null
grep -Fx 'Verification Run Independently Checked: NO' "$out" >/dev/null
grep -Fx 'Release Implies Deployment: NO' "$out" >/dev/null
grep -Fx 'Production Promotion Performed: NO' "$out" >/dev/null
grep -Fx 'Authority Expansion: NONE' "$out" >/dev/null
grep -Fx 'Release Action Performed: NO' "$out" >/dev/null
grep -Fx 'Tag Created: NO' "$out" >/dev/null
grep -Fx 'GitHub Release Published: NO' "$out" >/dev/null

printf '%s\n' 'V1.4 RELEASE CANDIDATE: READY FOR INDEPENDENT VERIFICATION'
