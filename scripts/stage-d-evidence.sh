#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  stage-d-evidence.sh preflight <evidence-dir>
  stage-d-evidence.sh capture <evidence-dir>
  stage-d-evidence.sh record-replacement <evidence-dir>
  stage-d-evidence.sh verify-survival <evidence-dir>
  stage-d-evidence.sh verify-absence <evidence-dir>
  stage-d-evidence.sh restore-verify <evidence-dir>

Required environment for network phases:
  NEXUS_BASE_URL   Public HTTPS base URL of the deployed NEXUS service
  NEXUS_API_TOKEN  Operator-held bearer token (never written to evidence)

For capture:
  NEXUS_WORKSPACE_ID    Existing workspace to use as the persistence witness
  NEXUS_DEPLOYED_COMMIT Exact 40-character repository commit deployed on host

For record-replacement (after a real provider service/container replacement):
  NEXUS_REPLACEMENT_EVENT_ID  Sanitized provider/operator replacement identifier
  NEXUS_REPLACEMENT_AT_UTC    UTC timestamp in YYYY-MM-DDTHH:MM:SSZ form
  NEXUS_REPLACEMENT_COMMIT    Exact 40-character commit running after replacement

For verify-absence (after destructive removal of the witness backing state):
  NEXUS_DESTRUCTIVE_EVENT_ID  Sanitized provider/operator destructive-test identifier
  NEXUS_DESTRUCTIVE_AT_UTC    UTC timestamp in YYYY-MM-DDTHH:MM:SSZ form

The evidence directory must be stored independently of the host under test.
Lifecycle event identifiers are corroborating operator/provider evidence; they are
not a substitute for the network survival and absence checks performed here.
EOF
}

mode="${1:-}"
evidence_dir="${2:-}"
if [[ -z "$mode" || -z "$evidence_dir" ]]; then
  usage >&2
  exit 2
fi

mkdir -p "$evidence_dir"

require_network_env() {
  : "${NEXUS_BASE_URL:?NEXUS_BASE_URL is required}"
  : "${NEXUS_API_TOKEN:?NEXUS_API_TOKEN is required}"
  python3 - "$NEXUS_BASE_URL" <<'PY'
import sys
from urllib.parse import urlsplit
u = urlsplit(sys.argv[1])
if u.scheme != 'https' or not u.hostname:
    raise SystemExit('NEXUS_BASE_URL must be an HTTPS origin')
if u.username or u.password or u.query or u.fragment:
    raise SystemExit('NEXUS_BASE_URL must not contain credentials, query, or fragment')
if u.path not in ('', '/'):
    raise SystemExit('NEXUS_BASE_URL must not contain a path prefix')
PY
}

canonical_equal() {
  python3 - "$1" "$2" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as a, open(sys.argv[2], encoding="utf-8") as b:
    if json.load(a) != json.load(b):
        raise SystemExit(1)
PY
}

snapshot_workspace_id() {
  python3 - "$1" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    data = json.load(f)
workspace_id = data.get("workspace", {}).get("id")
if not isinstance(workspace_id, str) or not workspace_id:
    raise SystemExit("snapshot workspace.id is missing")
print(workspace_id)
PY
}

snapshot_sha() {
  sha256sum "$1" | awk '{print $1}'
}

require_capture() {
  test -f "$evidence_dir/before.json"
  test -f "$evidence_dir/before.sha256"
  test -f "$evidence_dir/workspace-id.txt"
  test -f "$evidence_dir/deployed-commit.txt"
  test -f "$evidence_dir/result-capture.txt"
  grep -Fx 'Status: PASS' "$evidence_dir/result-capture.txt" >/dev/null
  local expected
  expected="$(tr -d '\r\n' < "$evidence_dir/before.sha256")"
  [[ "$expected" =~ ^[0-9a-f]{64}$ ]]
  test "$(snapshot_sha "$evidence_dir/before.json")" = "$expected"
}

validate_event_id() {
  local value="$1"
  [[ "$value" =~ ^[A-Za-z0-9._:@/+\=-]{1,200}$ ]] || {
    echo 'lifecycle event id contains unsupported characters or has invalid length' >&2
    exit 1
  }
  if printf '%s' "$value" | grep -Eqi 'authorization|bearer|token|secret|password'; then
    echo 'lifecycle event id contains credential-like terminology' >&2
    exit 1
  fi
}

validate_utc_timestamp() {
  local value="$1"
  [[ "$value" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]] || {
    echo 'lifecycle timestamp must use YYYY-MM-DDTHH:MM:SSZ' >&2
    exit 1
  }
  python3 - "$value" <<'PY'
import datetime, sys
try:
    datetime.datetime.strptime(sys.argv[1], '%Y-%m-%dT%H:%M:%SZ')
except ValueError as e:
    raise SystemExit(str(e))
PY
}

assert_no_credentials() {
  local file="$1"
  if grep -Eqi 'authorization:[[:space:]]*bearer|NEXUS_API_TOKEN=|Bearer[[:space:]]+[A-Za-z0-9._~+/=-]+' "$file"; then
    echo "credential-like material detected in evidence file: $file" >&2
    exit 1
  fi
}

write_snapshot_result() {
  local phase="$1"
  local status="$2"
  local sha="$3"
  cat > "$evidence_dir/result-${phase}.txt" <<EOF
Stage D Phase: ${phase}
Status: ${status}
Workspace Snapshot SHA-256: ${sha}
Token Recorded: NO
Authority Expansion: NONE
Epistemic Claim: operational persistence/recovery only
EOF
  assert_no_credentials "$evidence_dir/result-${phase}.txt"
}

case "$mode" in
  preflight)
    require_network_env
    base="${NEXUS_BASE_URL%/}"
    curl --fail --silent --show-error "$base/" >/dev/null

    missing_status="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
      "$base/v1/workspaces/__nexus_stage_d_preflight__")"
    [[ "$missing_status" == "401" ]] || {
      echo "protected route without bearer returned ${missing_status}, expected 401" >&2
      exit 1
    }

    wrong_status="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
      -H 'authorization: Bearer __nexus_stage_d_intentionally_invalid__' \
      "$base/v1/workspaces/__nexus_stage_d_preflight__")"
    [[ "$wrong_status" == "401" ]] || {
      echo "protected route with wrong bearer returned ${wrong_status}, expected 401" >&2
      exit 1
    }

    cat > "$evidence_dir/result-preflight.txt" <<'EOF'
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
    assert_no_credentials "$evidence_dir/result-preflight.txt"
    echo 'Stage D preflight PASS'
    ;;

  capture)
    require_network_env
    test -f "$evidence_dir/result-preflight.txt" || {
      echo 'Stage D preflight evidence is required before capture' >&2
      exit 1
    }
    grep -Fx 'Status: PASS' "$evidence_dir/result-preflight.txt" >/dev/null
    : "${NEXUS_WORKSPACE_ID:?NEXUS_WORKSPACE_ID is required for capture}"
    : "${NEXUS_DEPLOYED_COMMIT:?NEXUS_DEPLOYED_COMMIT is required for capture}"
    [[ "$NEXUS_DEPLOYED_COMMIT" =~ ^[0-9a-f]{40}$ ]] || {
      echo 'NEXUS_DEPLOYED_COMMIT must be a full 40-character lowercase SHA' >&2
      exit 1
    }
    before="$evidence_dir/before.json"
    NEXUS_WORKSPACE_ID="$NEXUS_WORKSPACE_ID" \
      bash "$(dirname "$0")/workspace-backup.sh" "$before" >/dev/null
    workspace_id="$(snapshot_workspace_id "$before")"
    if [[ "$workspace_id" != "$NEXUS_WORKSPACE_ID" ]]; then
      echo 'captured workspace id does not match requested workspace' >&2
      exit 1
    fi
    sha="$(snapshot_sha "$before")"
    printf '%s\n' "$workspace_id" > "$evidence_dir/workspace-id.txt"
    printf '%s\n' "$sha" > "$evidence_dir/before.sha256"
    printf '%s\n' "$NEXUS_DEPLOYED_COMMIT" > "$evidence_dir/deployed-commit.txt"
    write_snapshot_result capture PASS "$sha"
    printf 'Stage D capture PASS: %s\n' "$sha"
    ;;

  record-replacement)
    require_capture
    : "${NEXUS_REPLACEMENT_EVENT_ID:?NEXUS_REPLACEMENT_EVENT_ID is required}"
    : "${NEXUS_REPLACEMENT_AT_UTC:?NEXUS_REPLACEMENT_AT_UTC is required}"
    : "${NEXUS_REPLACEMENT_COMMIT:?NEXUS_REPLACEMENT_COMMIT is required}"
    validate_event_id "$NEXUS_REPLACEMENT_EVENT_ID"
    validate_utc_timestamp "$NEXUS_REPLACEMENT_AT_UTC"
    [[ "$NEXUS_REPLACEMENT_COMMIT" =~ ^[0-9a-f]{40}$ ]] || {
      echo 'NEXUS_REPLACEMENT_COMMIT must be a full 40-character lowercase SHA' >&2
      exit 1
    }
    deployed_commit="$(tr -d '\r\n' < "$evidence_dir/deployed-commit.txt")"
    [[ "$NEXUS_REPLACEMENT_COMMIT" == "$deployed_commit" ]] || {
      echo 'replacement commit does not match the captured deployed commit' >&2
      exit 1
    }
    cat > "$evidence_dir/replacement-event.txt" <<EOF
Lifecycle Event: service-replacement
Event ID: ${NEXUS_REPLACEMENT_EVENT_ID}
Event At UTC: ${NEXUS_REPLACEMENT_AT_UTC}
Deployed Commit: ${NEXUS_REPLACEMENT_COMMIT}
Token Recorded: NO
Authority Expansion: NONE
Epistemic Claim: operator/provider lifecycle corroboration only
EOF
    assert_no_credentials "$evidence_dir/replacement-event.txt"
    echo 'Stage D replacement event recorded'
    ;;

  verify-survival)
    require_network_env
    require_capture
    test -f "$evidence_dir/replacement-event.txt" || {
      echo 'replacement-event.txt is required before survival verification' >&2
      exit 1
    }
    grep -Fx 'Lifecycle Event: service-replacement' "$evidence_dir/replacement-event.txt" >/dev/null
    deployed_commit="$(tr -d '\r\n' < "$evidence_dir/deployed-commit.txt")"
    grep -Fx "Deployed Commit: ${deployed_commit}" "$evidence_dir/replacement-event.txt" >/dev/null
    before="$evidence_dir/before.json"
    workspace_id="$(snapshot_workspace_id "$before")"
    after="$evidence_dir/after-survival.json"
    curl --fail --silent --show-error \
      -H "authorization: Bearer ${NEXUS_API_TOKEN}" \
      "${NEXUS_BASE_URL%/}/v1/workspaces/${workspace_id}" \
      > "$after"
    python3 -m json.tool "$after" >/dev/null
    canonical_equal "$before" "$after"
    sha="$(snapshot_sha "$before")"
    test "$sha" = "$(tr -d '\r\n' < "$evidence_dir/before.sha256")"
    write_snapshot_result survival PASS "$sha"
    printf 'Stage D survival PASS: %s\n' "$sha"
    ;;

  verify-absence)
    require_network_env
    require_capture
    test -f "$evidence_dir/result-survival.txt" || {
      echo 'survival PASS is required before destructive absence verification' >&2
      exit 1
    }
    grep -Fx 'Status: PASS' "$evidence_dir/result-survival.txt" >/dev/null
    : "${NEXUS_DESTRUCTIVE_EVENT_ID:?NEXUS_DESTRUCTIVE_EVENT_ID is required}"
    : "${NEXUS_DESTRUCTIVE_AT_UTC:?NEXUS_DESTRUCTIVE_AT_UTC is required}"
    validate_event_id "$NEXUS_DESTRUCTIVE_EVENT_ID"
    validate_utc_timestamp "$NEXUS_DESTRUCTIVE_AT_UTC"

    before="$evidence_dir/before.json"
    workspace_id="$(snapshot_workspace_id "$before")"
    body="$evidence_dir/absence-response.json"
    status="$(curl --silent --show-error --output "$body" --write-out '%{http_code}' \
      -H "authorization: Bearer ${NEXUS_API_TOKEN}" \
      "${NEXUS_BASE_URL%/}/v1/workspaces/${workspace_id}")"
    [[ "$status" == "404" ]] || {
      echo "destructive absence check returned ${status}, expected 404" >&2
      exit 1
    }
    python3 - "$body" <<'PY'
import json, sys
with open(sys.argv[1], encoding='utf-8') as f:
    data = json.load(f)
if data != {'error': 'workspace_not_found'}:
    raise SystemExit('unexpected absence response body')
PY
    sha="$(snapshot_sha "$before")"
    cat > "$evidence_dir/destructive-event.txt" <<EOF
Lifecycle Event: destructive-backing-state-removal
Event ID: ${NEXUS_DESTRUCTIVE_EVENT_ID}
Event At UTC: ${NEXUS_DESTRUCTIVE_AT_UTC}
Observed HTTP Status: 404
Observed Error: workspace_not_found
Token Recorded: NO
Authority Expansion: NONE
Epistemic Claim: operator action plus observed workspace absence only
EOF
    assert_no_credentials "$evidence_dir/destructive-event.txt"
    write_snapshot_result absence PASS "$sha"
    echo 'Stage D destructive absence PASS'
    ;;

  restore-verify)
    require_network_env
    require_capture
    test -f "$evidence_dir/result-absence.txt" || {
      echo 'destructive absence PASS is required before restore verification' >&2
      exit 1
    }
    test -f "$evidence_dir/destructive-event.txt"
    grep -Fx 'Status: PASS' "$evidence_dir/result-absence.txt" >/dev/null
    grep -Fx 'Observed HTTP Status: 404' "$evidence_dir/destructive-event.txt" >/dev/null
    before="$evidence_dir/before.json"
    workspace_id="$(snapshot_workspace_id "$before")"
    NEXUS_BASE_URL="$NEXUS_BASE_URL" NEXUS_API_TOKEN="$NEXUS_API_TOKEN" \
      bash "$(dirname "$0")/workspace-restore.sh" "$before" >/dev/null
    restored="$evidence_dir/after-restore.json"
    curl --fail --silent --show-error \
      -H "authorization: Bearer ${NEXUS_API_TOKEN}" \
      "${NEXUS_BASE_URL%/}/v1/workspaces/${workspace_id}" \
      > "$restored"
    python3 -m json.tool "$restored" >/dev/null
    canonical_equal "$before" "$restored"
    sha="$(snapshot_sha "$before")"
    test "$sha" = "$(tr -d '\r\n' < "$evidence_dir/before.sha256")"
    write_snapshot_result restore PASS "$sha"
    printf 'Stage D restore PASS: %s\n' "$sha"
    ;;

  *)
    usage >&2
    exit 2
    ;;
esac
