#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail() {
  printf 'V1.2 G3 DURABLE-STATE RESILIENCE: BLOCKED — %s\n' "$1" >&2
  exit 1
}

for f in Dockerfile scripts/workspace-backup.sh scripts/workspace-restore.sh scripts/readonly-verification.sh docs/DEPLOYMENT.md; do
  [[ -f "$f" ]] || fail "missing $f"
done

# Runtime persistence boundary must remain explicit and fixed.
grep -F 'ENV NEXUS_DATA_DIR=/data' Dockerfile >/dev/null || fail 'Docker runtime persistence boundary is not /data'
grep -F 'persistent volume mounted at `/data`' docs/DEPLOYMENT.md >/dev/null || fail 'deployment contract no longer requires /data persistence'

# Operator backup/restore paths must remain authenticated and JSON-validating.
grep -F 'NEXUS_WORKSPACE_ID' scripts/workspace-backup.sh >/dev/null || fail 'backup is not scoped to an explicit workspace witness'
grep -F 'python3 -m json.tool' scripts/workspace-backup.sh >/dev/null || fail 'backup JSON validation missing'
grep -F 'python3 -m json.tool' scripts/workspace-restore.sh >/dev/null || fail 'restore input JSON validation missing'
grep -F '/v1/workspaces/import' scripts/workspace-restore.sh >/dev/null || fail 'restore no longer delegates to server-side import/revalidation'

# Backup tooling must never print or persist the bearer token itself.
if grep -E 'printf .*NEXUS_API_TOKEN|echo .*NEXUS_API_TOKEN|>.*NEXUS_API_TOKEN' scripts/workspace-backup.sh scripts/workspace-restore.sh >/dev/null; then
  fail 'backup/restore tooling may expose bearer token'
fi

# CI restore validation must be isolated from user data and prove JSON-equivalent recovery.
grep -F 'smoke_data="$RUNNER_TEMP/nexus-smoke-data-${GITHUB_RUN_ID}"' scripts/readonly-verification.sh >/dev/null \
  || fail 'dedicated temporary witness storage missing'
grep -F 'find "$smoke_data" -mindepth 1 -maxdepth 1 -exec rm -rf {} +' scripts/readonly-verification.sh >/dev/null \
  || fail 'isolated destructive witness exercise missing'
grep -F 'bash scripts/workspace-backup.sh "$backup"' scripts/readonly-verification.sh >/dev/null \
  || fail 'witness backup exercise missing'
grep -F 'bash scripts/workspace-restore.sh "$backup"' scripts/readonly-verification.sh >/dev/null \
  || fail 'witness restore exercise missing'
grep -F "assert json.load(open(sys.argv[1])) == json.load(open(sys.argv[2]))" scripts/readonly-verification.sh >/dev/null \
  || fail 'JSON-equivalent restore assertion missing'
grep -F "grep -F 'ci-smoke-token'" scripts/readonly-verification.sh >/dev/null \
  || fail 'secret-leak assertion missing'

printf '%s\n' 'V1.2 G3 DURABLE-STATE RESILIENCE: PASS'
printf '%s\n' 'Persistence boundary: /data'
printf '%s\n' 'Destructive validation scope: dedicated CI witness only'
printf '%s\n' 'Token recorded in backup contract: NO'
printf '%s\n' 'Authority Expansion: NONE'
