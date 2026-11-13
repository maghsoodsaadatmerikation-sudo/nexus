#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${NEXUS_BASE_URL:?NEXUS_BASE_URL is required}"
: "${NEXUS_API_TOKEN:?NEXUS_API_TOKEN is required}"
snapshot="${1:?snapshot JSON path is required}"
if (( $# != 1 )); then
  echo 'WORKSPACE RESTORE: BLOCKED (exactly one snapshot argument required)' >&2
  exit 1
fi

# Validate the origin and the on-disk snapshot without printing either private
# values or a token. Restrict plaintext to the CI/operator loopback endpoint.
origin="$(python3 - "$snapshot" "$ROOT/scripts/workspace-backup.py" <<'PY'
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

path = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location('nexus_workspace_backup', sys.argv[2])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
try:
    st = path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or not 0 < st.st_size <= mod.MAX_BYTES:
        raise ValueError('unsafe snapshot path or size')
    token = os.getenv('NEXUS_API_TOKEN', '')
    if not token or not token.isascii() or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise ValueError('invalid bearer credential')
    with path.open('rb') as stream:
        def no_duplicates(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('duplicate JSON member')
                result[key] = value
            return result
        document = json.load(stream, object_pairs_hook=no_duplicates)
    if not (type(document) is dict and
            type(document.get('schema_version')) is int and
            type(document.get('workspace')) is dict and
            isinstance(document['workspace'].get('id'), str) and
            type(document.get('events')) is list):
        raise ValueError('not a NEXUS workspace snapshot')
    print(mod.origin_url(os.environ['NEXUS_BASE_URL']))
except (OSError, UnicodeError, ValueError):
    print('WORKSPACE RESTORE: BLOCKED (invalid origin, token, or snapshot)', file=sys.stderr)
    sys.exit(1)
PY
)"

# curl reads the header from stdin, not argv or an on-disk header file.
# No -L; a redirect must never forward the bearer token to another origin.
code="$(printf 'Authorization: Bearer %s\n' "$NEXUS_API_TOKEN" |
  curl --fail --silent --show-error --max-time 120 --connect-timeout 10 \
    --proto '=http,https' --retry 0 \
    -X POST -H 'content-type: application/json' -H @- \
    --data-binary "@${snapshot}" -o /dev/null -w '%{http_code}' \
    "${origin}/v1/workspaces/import")"
if [[ "$code" != 201 ]]; then
  echo 'WORKSPACE RESTORE: BLOCKED (unexpected HTTP import status)' >&2
  exit 1
fi
printf '%s\n' 'Workspace restore accepted by NEXUS (single-workspace import only).'
