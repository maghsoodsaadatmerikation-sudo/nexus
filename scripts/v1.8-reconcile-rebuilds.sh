#!/usr/bin/env bash
set -euo pipefail

left="${1:?build A digest file required}"
right="${2:?build B digest file required}"
out="${3:-v1.8-reproducibility-evidence.json}"
candidate="${4:?candidate SHA required}"
verification_run="${5:?NEXUS Verification run required}"
rebuild_run="${6:?rebuild run required}"

fail() { printf 'V1.8 REBUILD RECONCILIATION: BLOCKED — %s\n' "$1" >&2; exit 1; }

[[ "$candidate" =~ ^[0-9a-f]{40}$ ]] || fail 'candidate SHA invalid'
[[ "$verification_run" =~ ^[0-9]+$ ]] || fail 'verification run invalid'
[[ "$rebuild_run" =~ ^[0-9]+$ ]] || fail 'rebuild run invalid'
[[ -f "$left" && -f "$right" ]] || fail 'digest evidence missing'

a="$(awk '{print $1}' "$left")"
b="$(awk '{print $1}' "$right")"
[[ "$a" =~ ^[0-9a-f]{64}$ ]] || fail 'build A digest invalid'
[[ "$b" =~ ^[0-9a-f]{64}$ ]] || fail 'build B digest invalid'
[[ "$a" == "$b" ]] || fail 'independent executable digests differ'

python3 - "$out" "$candidate" "$verification_run" "$rebuild_run" "$a" <<'PY'
import json,sys
out,candidate,verify_run,rebuild_run,digest=sys.argv[1:]
obj={
  'schema':'nexus.v1.8.independent-rebuild-evidence.v1',
  'status':'PASS',
  'candidate_sha':candidate,
  'nexus_verification_run_id':verify_run,
  'independent_rebuild_run_id':rebuild_run,
  'builders':{
    'a':{'environment':'github-hosted ubuntu-24.04','executable_sha256':digest},
    'b':{'environment':'github-hosted ubuntu-24.04','executable_sha256':digest}
  },
  'executable_digest_match':True,
  'production_mutation_performed':False,
  'paid_upgrade_required':False,
  'secret_value_recorded':False,
  'authority_expansion':'NONE',
  'claim_boundary':'Byte-identical gateway executable across the two independent GitHub-hosted rebuild jobs in this run under the recorded pinned build definition only.'
}
with open(out,'w',encoding='utf-8') as f:
    json.dump(obj,f,indent=2,sort_keys=True)
    f.write('\n')
PY

printf 'V1.8 INDEPENDENT REBUILD: PASS\nExecutable SHA-256: %s\nAuthority Expansion: NONE\n' "$a"
