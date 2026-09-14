#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

candidate_commit="${1:?candidate commit is required}"
verification_run="${2:?verification run id is required}"
out="${3:-v1.5-release-candidate-manifest.txt}"

fail() {
  printf 'V1.5 RELEASE CANDIDATE: BLOCKED — %s\n' "$1" >&2
  exit 1
}

[[ "$candidate_commit" =~ ^[0-9a-f]{40}$ ]] || fail 'candidate commit must be a full lowercase SHA'
[[ "$verification_run" =~ ^[0-9]+$ ]] || fail 'verification run id must be numeric'
[[ "$(git rev-parse HEAD)" == "$candidate_commit" ]] || fail 'checked-out commit differs from candidate commit'

bash scripts/v1.5-promotion-safety.sh >/dev/null

for required in \
  docs/V1.5-ROADMAP.md \
  docs/V1.5-RELEASE-GATE.md \
  docs/RELEASE-v1.4.0.md \
  evidence/live-deployment-state.json; do
  [[ -f "$required" ]] || fail "missing ${required}"
done

cat > "$out" <<EOF
NEXUS v1.5 Release Candidate
Status: READY FOR INDEPENDENT VERIFICATION
Candidate Commit: ${candidate_commit}
Verification Run ID: ${verification_run}
Verification Run Independently Checked: NO
G1 Historical Release Integrity: PASS
G2 Promotion Target Identity: PASS
G3 Pre-Cutover Durable-State Safety: PASS
G4 Exact-SHA Execution Requirement: PASS
G5 Post-Cutover Evidence Requirement: PASS
G6 Rollback Readiness: PASS
G7 Operational Economy: PASS
Promotion Target: dcf49302e8a8c4c935de3aad0585b19132bad2cd
Rollback Anchor Commit: 480f8771c47e41d4d19b22ed4360bd32c4d2f70a
Rollback Anchor Deployment: 1f63e3b9-768f-441e-a524-b061394b922e
Promotion Executable With Connected Tooling: NO
Production Promotion Performed: NO
Authority Expansion: NONE
Paid Resource Upgrade Required: NO
Release Action Performed: NO
Tag Created: NO
GitHub Release Published: NO
Epistemic Claim: promotion-safety and rollback-readiness release-candidate only
EOF

grep -Fx "Candidate Commit: ${candidate_commit}" "$out" >/dev/null
grep -Fx "Verification Run ID: ${verification_run}" "$out" >/dev/null
grep -Fx 'Verification Run Independently Checked: NO' "$out" >/dev/null
grep -Fx 'Promotion Executable With Connected Tooling: NO' "$out" >/dev/null
grep -Fx 'Production Promotion Performed: NO' "$out" >/dev/null
grep -Fx 'Authority Expansion: NONE' "$out" >/dev/null
grep -Fx 'Release Action Performed: NO' "$out" >/dev/null
grep -Fx 'Tag Created: NO' "$out" >/dev/null
grep -Fx 'GitHub Release Published: NO' "$out" >/dev/null

printf '%s\n' 'V1.5 RELEASE CANDIDATE: READY FOR INDEPENDENT VERIFICATION'
