#!/usr/bin/env bash
set -euo pipefail

: "${NEXUS_BASE_URL:?NEXUS_BASE_URL is required}"
: "${NEXUS_API_TOKEN:?NEXUS_API_TOKEN is required}"

snapshot="${1:?snapshot JSON path is required}"
python3 -m json.tool "$snapshot" >/dev/null

curl --fail --silent --show-error \
  -X POST \
  -H 'content-type: application/json' \
  -H "authorization: Bearer ${NEXUS_API_TOKEN}" \
  --data-binary "@${snapshot}" \
  "${NEXUS_BASE_URL%/}/v1/workspaces/import"

printf '\nRestore accepted and revalidated by NEXUS.\n'
