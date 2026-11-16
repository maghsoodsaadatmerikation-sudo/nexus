#!/usr/bin/env bash
# Exact source of independently observed public assets; provider deployment commit is not inferred.
# Candidate source is tested separately and NEVER silently treated as published.
set -euo pipefail
baseline=f90162d46040be03341769f3c30206cb7f0f476d
test -n "${RUNNER_TEMP:-}"
target="$RUNNER_TEMP/nexus-live-pilot"
test ! -e "$target"
mkdir -m 700 "$target"
# Public-browser assertions must come from the same immutable revision as
# the HTML they exercise. Copying candidate scripts here would silently mix
# a newer test contract with an older deployed app and produce a false red.
# Candidate checks remain in their separate PR/offline CI workflows.
git archive "$baseline" web public scripts | tar -x -C "$target"
python3 - "$baseline" "$target" <<'PY'
import hashlib,json,sys
from pathlib import Path
source=Path('web/offline-pilot.html').read_bytes()
live=(Path(sys.argv[2])/'web/offline-pilot.html').read_bytes()
print(json.dumps({'asset_source_commit':sys.argv[1],'provider_deployment_commit_verified':False,
 'expected_published_html_sha256':hashlib.sha256(live).hexdigest(),
 'candidate_html_sha256':hashlib.sha256(source).hexdigest(),
 'candidate_equals_published_source':source==live,
 'candidate_promoted_by_this_step':False,'authority':'none'}))
PY
