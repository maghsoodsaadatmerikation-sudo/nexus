#!/usr/bin/env bash
# Observe only the public HTTPS authentication boundary. No credential is used.
# A PASS is NOT a workspace-snapshot, durable-storage, or release attestation.
set -euo pipefail
: "${NEXUS_BASE_URL:?NEXUS_BASE_URL must be supplied}"

python3 - "$NEXUS_BASE_URL" <<'PY'
import sys
from urllib.parse import urlsplit
u = urlsplit(sys.argv[1])
if (u.scheme != "https" or not u.hostname or u.username or u.password
        or u.query or u.fragment or u.path not in ("", "/")
        or (u.port not in (None, 443))):
    raise SystemExit("NEXUS_BASE_URL must be a credential-free HTTPS origin")
PY

url="${NEXUS_BASE_URL%/}/v1/workspaces/__nexus_stage_d_preflight__"

probe() {
  local mode="$1" code="" transport_exit=0
  local -a header=()
  if [[ "$mode" == wrong ]]; then
    header=(-H 'authorization: Bearer __nexus_stage_d_intentionally_invalid__')
  fi
  code="$(curl --silent --show-error --proto '=https' \
    --connect-timeout 10 --max-time 30 --max-filesize 65536 \
    --output /dev/null --write-out '%{http_code}' "${header[@]}" "$url" 2>/dev/null)" || transport_exit=$?
  [[ "$code" =~ ^[0-9]{3}$ ]] || code=000
  printf '%s %s\n' "$code" "$transport_exit"
}
read -r missing_status missing_exit < <(probe missing)
read -r wrong_status wrong_exit < <(probe wrong)
status=FAIL
if [[ "$missing_status" == 401 && "$wrong_status" == 401 && "$missing_exit" == 0 && "$wrong_exit" == 0 ]]; then
  status=PASS
fi

jq -n \
  --arg status "$status" \
  --arg endpoint "${NEXUS_BASE_URL%/}/v1/workspaces/__nexus_stage_d_preflight__" \
  --arg missing_status "$missing_status" --arg wrong_status "$wrong_status" \
  --argjson missing_exit "$missing_exit" --argjson wrong_exit "$wrong_exit" \
  --arg observed_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg observer_commit "${GITHUB_SHA:-unknown}" \
  --arg run_id "${GITHUB_RUN_ID:-local}" \
  '{schema:"nexus.stage-d.public-auth-boundary.v1", status:$status, endpoint:$endpoint,
    observed_at:$observed_at, observer_commit:$observer_commit, workflow_run_id:$run_id,
    missing_bearer:{http_status:($missing_status|tonumber), transport_exit:$missing_exit},
    invalid_bearer:{http_status:($wrong_status|tonumber), transport_exit:$wrong_exit},
    credentials_used:false, response_bodies_recorded:false,
    proves_persistence:false, proves_recovery:false, grants_authority:false,
    mutation_scope:{deployment:false, production_write:false, volume_operation:false,
      authorization:false, release:false, seal:false}}' > stage-d-public-auth-evidence.json
sha256sum stage-d-public-auth-evidence.json > stage-d-public-auth-evidence.sha256
echo "Stage D public auth boundary: $status"
[[ "$status" == PASS ]]
