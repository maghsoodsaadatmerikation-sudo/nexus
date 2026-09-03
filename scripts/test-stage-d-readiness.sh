#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
E="$TMP/evidence"
mkdir -p "$E"
COMMIT="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
RUN_ID="123456"

cat > "$E/result-preflight.txt" <<'EOF'
Stage D Phase: preflight
Status: PASS
Endpoint Scheme: HTTPS
Public Liveness: PASS
Missing Bearer Rejected: PASS
Wrong Bearer Rejected: PASS
Token Recorded: NO
Authority Expansion: NONE
Epistemic Claim: operational transport boundary only
EOF

cat > "$E/before.json" <<'EOF'
{"workspace":{"id":"stage-d-fixture"},"sequence":[]}
EOF
cp "$E/before.json" "$E/after-survival.json"
cp "$E/before.json" "$E/after-restore.json"
printf '%s\n' "$(sha256sum "$E/before.json" | awk '{print $1}')" > "$E/before.sha256"
printf '%s\n' 'stage-d-fixture' > "$E/workspace-id.txt"
printf '%s\n' "$COMMIT" > "$E/deployed-commit.txt"
SHA="$(cat "$E/before.sha256")"

write_result() {
  local phase="$1"
  cat > "$E/result-${phase}.txt" <<EOF
Stage D Phase: ${phase}
Status: PASS
Workspace Snapshot SHA-256: ${SHA}
Token Recorded: NO
Authority Expansion: NONE
Epistemic Claim: operational persistence/recovery only
EOF
}

write_result capture
write_result survival
write_result absence
write_result restore

NEXUS_REPLACEMENT_EVENT_ID='render-deploy-fixture-123' \
NEXUS_REPLACEMENT_AT_UTC='2026-09-03T10:00:00Z' \
NEXUS_REPLACEMENT_COMMIT="$COMMIT" \
  bash scripts/stage-d-evidence.sh record-replacement "$E" >/dev/null

cat > "$E/absence-response.json" <<'EOF'
{"error":"workspace_not_found"}
EOF
cat > "$E/destructive-event.txt" <<'EOF'
Lifecycle Event: destructive-backing-state-removal
Event ID: render-destructive-fixture-456
Event At UTC: 2026-09-03T10:05:00Z
Observed HTTP Status: 404
Observed Error: workspace_not_found
Token Recorded: NO
Authority Expansion: NONE
Epistemic Claim: operator action plus observed workspace absence only
EOF

READY="$TMP/readiness.out"
bash scripts/v1.1-release-readiness.sh "$E" "$COMMIT" > "$READY"
grep -Fx 'V1.1 RELEASE READINESS: PASS' "$READY" >/dev/null
grep -Fx 'Stage D HTTPS/Auth Preflight: PASS' "$READY" >/dev/null
grep -Fx 'Stage D Replacement Event: RECORDED' "$READY" >/dev/null
grep -Fx 'Stage D Destructive Absence: PASS' "$READY" >/dev/null

CANDIDATE="$TMP/candidate.txt"
bash scripts/v1.1-release-candidate.sh "$E" "$COMMIT" "$RUN_ID" "$CANDIDATE" >/dev/null
grep -Fx 'Status: READY FOR HUMAN RELEASE DECISION' "$CANDIDATE" >/dev/null
grep -Fx 'Verification Run Independently Checked: NO' "$CANDIDATE" >/dev/null
grep -Fx 'Stage D Destructive Absence: PASS' "$CANDIDATE" >/dev/null
grep -Fx 'Release Action Performed: NO' "$CANDIDATE" >/dev/null

# Missing replacement corroboration must fail closed.
mv "$E/replacement-event.txt" "$E/replacement-event.saved"
if bash scripts/v1.1-release-readiness.sh "$E" "$COMMIT" >"$TMP/missing.out" 2>"$TMP/missing.err"; then
  echo 'readiness incorrectly accepted missing replacement evidence' >&2
  exit 1
fi
grep -F 'missing Stage D evidence file: replacement-event.txt' "$TMP/missing.err" >/dev/null
mv "$E/replacement-event.saved" "$E/replacement-event.txt"

# A destructive marker without observed workspace_not_found must fail closed.
cp "$E/absence-response.json" "$TMP/absence.saved"
printf '%s\n' '{"error":"unexpected"}' > "$E/absence-response.json"
if bash scripts/v1.1-release-readiness.sh "$E" "$COMMIT" >"$TMP/absence.out" 2>"$TMP/absence.err"; then
  echo 'readiness incorrectly accepted invalid destructive absence evidence' >&2
  exit 1
fi
mv "$TMP/absence.saved" "$E/absence-response.json"

# Evidence bound to another commit must fail closed.
if bash scripts/v1.1-release-readiness.sh "$E" "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" >"$TMP/commit.out" 2>"$TMP/commit.err"; then
  echo 'readiness incorrectly accepted a different deployed commit' >&2
  exit 1
fi
grep -F 'Stage D evidence is not bound to the expected deployed commit' "$TMP/commit.err" >/dev/null

echo 'STAGE D LIFECYCLE READINESS TESTS: PASS'
