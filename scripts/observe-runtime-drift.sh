#!/usr/bin/env bash
# Read-only public observation. Evidence never authorizes deployment or release.
set -euo pipefail
: "${URL:?}" "${EXPECTED_DIGEST:?}"
[[ "$EXPECTED_DIGEST" =~ ^[0-9a-f]{64}$ ]] || exit 2
response="$(mktemp)"
trap 'rm -f "$response"' EXIT
transport_exit=0
code="$(curl --silent --location --output "$response" --write-out '%{http_code}' --max-time 30 --max-filesize 65536 "$URL" 2>/dev/null)" || transport_exit=$?
[[ "$code" =~ ^[0-9]{3}$ ]] || code=000
json_valid=false
# Require exactly one JSON object; never publish the raw body or arbitrary strings.
if jq -e -s 'length == 1 and (.[0] | type == "object")' "$response" >/dev/null 2>&1; then json_valid=true; fi
runtime_schema=unavailable
authority=unavailable
observed=""
if "$json_valid"; then
  runtime_schema="$(jq -r 'if .schema == "nexus.runtime-identity.v1" then .schema else "unexpected" end' "$response")"
  authority="$(jq -r 'if .authority == "non_authoritative_build_metadata" then .authority else "unexpected" end' "$response")"
  observed="$(jq -r 'if (.source_tree_sha256 | type) == "string" then .source_tree_sha256 else "" end' "$response")"
  [[ "$observed" =~ ^[0-9a-f]{64}$ ]] || observed=""
fi
digest_match=false
[[ "$observed" == "$EXPECTED_DIGEST" ]] && digest_match=true
status=FAIL
if [[ "$transport_exit" == 0 && "$code" == 200 && "$json_valid" == true && "$runtime_schema" == nexus.runtime-identity.v1 && "$authority" == non_authoritative_build_metadata && "$digest_match" == true ]]; then status=PASS; fi
jq -n --arg schema nexus.v1.9.runtime-drift-observation.v1 \
  --arg status "$status" --arg endpoint "$URL" --arg http_status "$code" \
  --argjson transport_exit "$transport_exit" --argjson json_valid "$json_valid" \
  --arg runtime_schema "$runtime_schema" --arg authority "$authority" \
  --arg expected "$EXPECTED_DIGEST" --arg observed "$observed" --argjson digest_match "$digest_match" \
  --arg run_id "${GITHUB_RUN_ID:-local}" --arg observer_commit "${GITHUB_SHA:-unknown}" \
  --arg observed_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  '{schema:$schema,status:$status,endpoint:$endpoint,http_status:($http_status|tonumber),transport_exit:$transport_exit,json_valid:$json_valid,runtime_schema:$runtime_schema,authority:$authority,expected_source_tree_sha256:$expected,observed_source_tree_sha256:$observed,digest_match:$digest_match,workflow_run_id:$run_id,observer_commit:$observer_commit,observed_at:$observed_at,mutation_scope:{production_write:false,deployment:false,rollback:false,promotion:false,authorization:false,human_judgment:false,policy_mutation:false}}' > v1.9-runtime-drift-evidence.json
sha256sum v1.9-runtime-drift-evidence.json > v1.9-runtime-drift-evidence.sha256
cat v1.9-runtime-drift-evidence.json
echo "V1.9 RUNTIME DRIFT WATCH: $status"
[[ "$status" == PASS ]]
