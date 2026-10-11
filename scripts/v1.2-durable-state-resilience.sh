#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail() {
  printf 'V1.2 G3 DURABLE-STATE RESILIENCE: BLOCKED — %s\n' "$1" >&2
  exit 1
}

for f in Dockerfile scripts/workspace-backup.sh scripts/workspace-restore.sh scripts/readonly-verification.sh docs/DEPLOYMENT.md scripts/data-snapshot.py docs/full-data-recovery.md artifact-05/src/main.rs artifact-05/src/lib.rs scripts/verify-data-recovery-http.py docs/gateway-health.md; do
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
python3 - <<'PYCLEANUP' || fail 'isolated destructive witness exercise missing'
from pathlib import Path
expected = "\n".join([
    'docker run --rm --user 0 --entrypoint sh \\',
    '  -v "$smoke_data:/data" nexus-ci-smoke \\',
    "  -c 'find /data -mindepth 1 -maxdepth 1 -exec rm -rf {} +'",
])
assert expected in Path('scripts/readonly-verification.sh').read_text()
PYCLEANUP
grep -F 'bash scripts/workspace-backup.sh "$backup"' scripts/readonly-verification.sh >/dev/null \
  || fail 'witness backup exercise missing'
grep -F 'bash scripts/workspace-restore.sh "$backup"' scripts/readonly-verification.sh >/dev/null \
  || fail 'witness restore exercise missing'
grep -F "assert json.load(open(sys.argv[1])) == json.load(open(sys.argv[2]))" scripts/readonly-verification.sh >/dev/null \
  || fail 'JSON-equivalent restore assertion missing'
grep -F "grep -F 'ci-smoke-token'" scripts/readonly-verification.sh >/dev/null \
  || fail 'secret-leak assertion missing'

grep -F 'volume_restore="$RUNNER_TEMP/nexus-full-data-restored-${GITHUB_RUN_ID}"' scripts/readonly-verification.sh >/dev/null \
  || fail 'isolated full-data restore target missing'
grep -F 'python3 scripts/data-snapshot.py backup "$smoke_data" "$volume_snapshot" --offline' scripts/readonly-verification.sh >/dev/null \
  || fail 'offline full-data backup exercise missing'
grep -F 'sudo python3 scripts/data-snapshot.py restore "$volume_snapshot" "$volume_restore" --offline --owner 10001:10001' scripts/readonly-verification.sh >/dev/null \
  || fail 'offline runtime-owned restore exercise missing'
grep -F 'scripts/verify-data-recovery-http.py "$base_url" "$volume_request_id" "$restored" --repeat' scripts/readonly-verification.sh >/dev/null \
  || fail 'full-data HTTP restart validation missing'
grep -F "echo 'FULL DATA VOLUME RECOVERY PASS'" scripts/readonly-verification.sh >/dev/null \
  || fail 'full-data recovery result missing'

grep -F '.with_recovery_gate(&data_root)' artifact-05/src/main.rs >/dev/null \
  || fail 'runtime recovery quarantine missing'
python3 - <<'PYQUARANTINE' || fail 'persistent recovery quarantine witness missing'
from pathlib import Path
check = 'scripts/verify-data-recovery-http.py "$base_url" "$volume_request_id" "$restored" --quarantined'
assert Path('scripts/readonly-verification.sh').read_text().count(check) == 2
PYQUARANTINE
grep -F 'sudo python3 scripts/data-snapshot.py resume "$volume_restore" --offline --acknowledge-replay-risk' scripts/readonly-verification.sh >/dev/null \
  || fail 'explicit offline replay-risk acknowledgment missing'

grep -F '.route("/readyz", get(readiness::<D>))' artifact-05/src/lib.rs >/dev/null \
  || fail 'gateway readiness route missing'
grep -F 'GET /livez HTTP/1.1' Dockerfile >/dev/null \
  || fail 'container liveness probe missing'
grep -F '("/readyz", 503 if args.quarantined else 200,' scripts/verify-data-recovery-http.py >/dev/null \
  || fail 'quarantine readiness HTTP witness missing'
grep -F 'Gateway Readiness: PASS' scripts/readonly-verification.sh >/dev/null \
  || fail 'gateway readiness evidence field missing'

# Missing-ledger drill must stay inside the already bounded synthetic mount.
python3 - <<'CHECK_STORAGE' || fail 'storage failure witness missing or unbounded'
from pathlib import Path
s = Path('scripts/readonly-verification.sh').read_text()
for operation in [
    'test -d /data/requests && test ! -e /data/requests.offline && mv /data/requests /data/requests.offline',
    'test ! -e /data/requests && mv /data/requests.offline /data/requests',
]:
    assert '-v "$smoke_data:/data" nexus-ci-smoke \\\n  -c \'%s\'' % operation in s
for phase in ['unavailable', 'repaired', 'restarted']:
    assert 'python3 scripts/verify-storage-failure-http.py "$base_url" "$volume_request_id" ' + phase in s
assert 'Storage Failure Recovery: PASS' in s
assert Path('scripts/verify-storage-failure-http.py').is_file()
assert Path('docs/gateway-storage-failure.md').is_file()
CHECK_STORAGE

python3 - <<'CHECK_FULL' || fail 'ENOSPC witness missing or unbounded'
from pathlib import Path
s = Path('scripts/verify-storage-full.py').read_text()
assert "'/data:rw,size=8m,uid=10001,gid=10001,mode=0700'" in s
assert "'--tmpfs'" in s and "'-p', '127.0.0.1::3000'" in s
assert not any(option in s for option in ["'--mount'", "'--volume'", "'-v'", "'--privileged'"])
assert "'No space left on device' in filled.stderr" in s
assert "'kill', '-TERM', old_pid" in s
assert 'status(failed, \'indeterminate\')' in s
assert Path('docs/gateway-storage-full.md').is_file()
h = Path('scripts/readonly-verification.sh').read_text()
assert 'python3 scripts/verify-storage-full.py nexus-ci-smoke "$GITHUB_RUN_ID"' in h
assert 'Storage Full Recovery: PASS' in h
assert '--tmpfs /tmp/nexus-test-enospc:rw,size=8m,mode=0777' in h
assert 'enospc_reservation_fails_before_delegation -- --ignored --exact --nocapture' in h
assert 'ENOSPC Before Delegation: PASS' in h

CHECK_FULL

printf '%s\n' 'V1.2 G3 DURABLE-STATE RESILIENCE: PASS'
printf '%s\n' 'Persistence boundary: /data'
printf '%s\n' 'Destructive validation scope: dedicated CI witness only'
printf '%s\n' 'Token recorded in backup contract: NO'
printf '%s\n' 'Authority Expansion: NONE'
