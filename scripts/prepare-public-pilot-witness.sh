#!/usr/bin/env bash
# Current deployed HTML/assets, with reviewed read-only observers from this checkout.
# Candidate source is tested separately and NEVER silently treated as published.
set -euo pipefail
baseline=1b9f1dbc4544cfc608229cb7a8464e60f08aaf40
test -n "${RUNNER_TEMP:-}"
target="$RUNNER_TEMP/nexus-live-pilot"
test ! -e "$target"
mkdir -m 700 "$target"
git archive "$baseline" web public | tar -x -C "$target"
cp -R scripts "$target/scripts"
python3 - "$baseline" "$target" <<'PY'
import hashlib,json,sys
from pathlib import Path
source=Path('web/offline-pilot.html').read_bytes()
live=(Path(sys.argv[2])/'web/offline-pilot.html').read_bytes()
print(json.dumps({'observed_source_commit':sys.argv[1],
 'expected_published_html_sha256':hashlib.sha256(live).hexdigest(),
 'candidate_html_sha256':hashlib.sha256(source).hexdigest(),
 'candidate_equals_published_source':source==live,
 'candidate_promoted_by_this_step':False,'authority':'none'}))
PY
