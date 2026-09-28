#!/usr/bin/env bash
set -euo pipefail

: "${NEXUS_BASE_URL:?NEXUS_BASE_URL is required}"
: "${NEXUS_API_TOKEN:?NEXUS_API_TOKEN is required}"
: "${NEXUS_WORKSPACE_ID:?NEXUS_WORKSPACE_ID is required}"

output="${1:-nexus-workspace-${NEXUS_WORKSPACE_ID}.json}"
tmp="${output}.tmp"
trap 'rm -f "$tmp"' EXIT

curl --fail --silent --show-error \
  -H "authorization: Bearer ${NEXUS_API_TOKEN}" \
  "${NEXUS_BASE_URL%/}/v1/workspaces/${NEXUS_WORKSPACE_ID}" \
  > "$tmp"

python3 -m json.tool "$tmp" >/dev/null
mv "$tmp" "$output"
trap - EXIT
printf 'Backup written: %s\n' "$output"
