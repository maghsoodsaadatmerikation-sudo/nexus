#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  stage-d-evidence.sh capture <evidence-dir>
  stage-d-evidence.sh verify-survival <evidence-dir>
  stage-d-evidence.sh restore-verify <evidence-dir>

Required environment:
  NEXUS_BASE_URL   Public HTTPS base URL of the deployed NEXUS service
  NEXUS_API_TOKEN  Operator-held bearer token (never written to evidence)

For capture only:
  NEXUS_WORKSPACE_ID    Existing workspace to use as the persistence witness
  NEXUS_DEPLOYED_COMMIT Exact 40-character repository commit deployed on host

The evidence directory must be stored independently of the host under test.
EOF
}

: "${NEXUS_BASE_URL:?NEXUS_BASE_URL is required}"
: "${NEXUS_API_TOKEN:?NEXUS_API_TOKEN is required}"

mode="${1:-}"
evidence_dir="${2:-}"
if [[ -z "$mode" || -z "$evidence_dir" ]]; then
  usage >&2
  exit 2
fi

mkdir -p "$evidence_dir"

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

write_result() {
  local phase="$1"
  local status="$2"
  local snapshot_sha="$3"
  cat > "$evidence_dir/result-${phase}.txt" <<EOF
Stage D Phase: ${phase}
Status: ${status}
Workspace Snapshot SHA-256: ${snapshot_sha}
Token Recorded: NO
Epistemic Claim: operational persistence/recovery only
EOF
}

case "$mode" in
  capture)
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
    snapshot_sha="$(sha256sum "$before" | awk '{print $1}')"
    printf '%s\n' "$workspace_id" > "$evidence_dir/workspace-id.txt"
    printf '%s\n' "$snapshot_sha" > "$evidence_dir/before.sha256"
    printf '%s\n' "$NEXUS_DEPLOYED_COMMIT" > "$evidence_dir/deployed-commit.txt"
    write_result capture PASS "$snapshot_sha"
    printf 'Stage D capture PASS: %s\n' "$snapshot_sha"
    ;;

  verify-survival)
    before="$evidence_dir/before.json"
    test -f "$before"
    test -f "$evidence_dir/deployed-commit.txt"
    workspace_id="$(snapshot_workspace_id "$before")"
    after="$evidence_dir/after-survival.json"
    curl --fail --silent --show-error \
      -H "authorization: Bearer ${NEXUS_API_TOKEN}" \
      "${NEXUS_BASE_URL%/}/v1/workspaces/${workspace_id}" \
      > "$after"
    python3 -m json.tool "$after" >/dev/null
    canonical_equal "$before" "$after"
    snapshot_sha="$(sha256sum "$before" | awk '{print $1}')"
    test "$(sha256sum "$before" | awk '{print $1}')" = "$(cat "$evidence_dir/before.sha256")"
    write_result survival PASS "$snapshot_sha"
    printf 'Stage D survival PASS: %s\n' "$snapshot_sha"
    ;;

  restore-verify)
    before="$evidence_dir/before.json"
    test -f "$before"
    test -f "$evidence_dir/deployed-commit.txt"
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
    snapshot_sha="$(sha256sum "$before" | awk '{print $1}')"
    test "$(sha256sum "$before" | awk '{print $1}')" = "$(cat "$evidence_dir/before.sha256")"
    write_result restore PASS "$snapshot_sha"
    printf 'Stage D restore PASS: %s\n' "$snapshot_sha"
    ;;

  *)
    usage >&2
    exit 2
    ;;
esac
