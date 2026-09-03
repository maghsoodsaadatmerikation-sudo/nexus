#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  v1.1-release-candidate.sh <stage-d-evidence-dir> <expected-deployed-commit> <verification-run-id> [output-manifest]

Creates an offline v1.1 release-candidate manifest only after the Stage E
release-readiness gate passes. It never creates a tag or publishes a release.
The verification run ID is recorded for independent GitHub cross-checking; this
script does not claim to verify GitHub remotely.
EOF
}

fail() {
  printf 'V1.1 RELEASE CANDIDATE: BLOCKED — %s\n' "$1" >&2
  exit 1
}

[[ $# -ge 3 && $# -le 4 ]] || { usage >&2; exit 2; }
evidence_dir="$1"
expected_commit="$2"
verification_run_id="$3"
output="${4:-v1.1-release-candidate-manifest.txt}"

[[ "$expected_commit" =~ ^[0-9a-f]{40}$ ]] || fail 'expected deployed commit must be a full 40-character lowercase SHA'
[[ "$verification_run_id" =~ ^[0-9]+$ ]] || fail 'verification run id must be numeric'

readiness_output="$(mktemp)"
trap 'rm -f "$readiness_output"' EXIT
if ! bash "$(dirname "$0")/v1.1-release-readiness.sh" "$evidence_dir" "$expected_commit" >"$readiness_output"; then
  fail 'Stage E release-readiness gate did not pass'
fi

grep -Fx 'V1.1 RELEASE READINESS: PASS' "$readiness_output" >/dev/null || fail 'Stage E PASS marker missing'
grep -Fx "Deployed Commit: ${expected_commit}" "$readiness_output" >/dev/null || fail 'Stage E commit binding mismatch'
grep -Fx 'Stage D HTTPS/Auth Preflight: PASS' "$readiness_output" >/dev/null || fail 'Stage D preflight marker missing'
grep -Fx 'Stage D Replacement Event: RECORDED' "$readiness_output" >/dev/null || fail 'Stage D replacement marker missing'
grep -Fx 'Stage D Survival: PASS' "$readiness_output" >/dev/null || fail 'Stage D survival marker missing'
grep -Fx 'Stage D Destructive Absence: PASS' "$readiness_output" >/dev/null || fail 'Stage D destructive absence marker missing'
grep -Fx 'Stage D Restore: PASS' "$readiness_output" >/dev/null || fail 'Stage D restore marker missing'
grep -Fx 'Release Action Performed: NO' "$readiness_output" >/dev/null || fail 'Stage E release-action boundary missing'

snapshot_sha="$(awk -F': ' '/^Workspace Snapshot SHA-256:/ {print $2}' "$readiness_output")"
[[ "$snapshot_sha" =~ ^[0-9a-f]{64}$ ]] || fail 'invalid Stage D snapshot hash'

stage_d_sha="$(sha256sum "$(dirname "$0")/stage-d-evidence.sh" | awk '{print $1}')"
readiness_sha="$(sha256sum "$(dirname "$0")/v1.1-release-readiness.sh" | awk '{print $1}')"

cat > "$output" <<EOF
NEXUS v1.1 Release Candidate
Status: READY FOR HUMAN RELEASE DECISION
Deployed Commit: ${expected_commit}
Verification Run ID: ${verification_run_id}
Verification Run Independently Checked: NO
Workspace Snapshot SHA-256: ${snapshot_sha}
Stage D Evidence Harness SHA-256: ${stage_d_sha}
Stage E Readiness Gate SHA-256: ${readiness_sha}
Stage D HTTPS/Auth Preflight: PASS
Stage D Capture: PASS
Stage D Replacement Event: RECORDED
Stage D Survival: PASS
Stage D Destructive Absence: PASS
Stage D Restore: PASS
Stage D: PASS
Stage E: PASS
Authority Expansion: NONE
Release Action Performed: NO
Tag Created: NO
GitHub Release Published: NO
Epistemic Claim: operational release-candidate readiness only
EOF

printf 'V1.1 RELEASE CANDIDATE: READY\nManifest: %s\n' "$output"
