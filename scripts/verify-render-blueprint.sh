#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

: "${GITHUB_SHA:?GITHUB_SHA is required}"
: "${GITHUB_RUN_ID:?GITHUB_RUN_ID is required}"

[[ "$GITHUB_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo 'GITHUB_SHA must be a full 40-character lowercase SHA' >&2
  exit 1
}

test "$(git rev-parse HEAD)" = "$GITHUB_SHA"
test -f render.yaml
test -f docs/RENDER-STAGE-D.md

python3 - <<'PY'
from pathlib import Path
import re

text = Path('render.yaml').read_text(encoding='utf-8')

required = [
    'type: web',
    'runtime: docker',
    'plan: 0.5c-512mb',
    'region: frankfurt',
    'dockerfilePath: ./Dockerfile',
    'autoDeployTrigger: checksPass',
    'healthCheckPath: /',
    'numInstances: 1',
    'mountPath: /data',
    'sizeGB: 1',
    'key: NEXUS_DATA_DIR',
    'value: /data',
    'key: NEXUS_BIND_ADDR',
    'value: 0.0.0.0:3000',
]
for item in required:
    if item not in text:
        raise SystemExit(f'missing required Render Stage D contract field: {item}')

if re.search(r'^\s*plan:\s*free\s*$', text, re.M):
    raise SystemExit('Render Stage D must not use the free ephemeral compute plan')

secret_block = re.search(
    r'-\s+key:\s*NEXUS_API_TOKEN\s*\n(?P<body>(?:\s{8,}.*\n?)*)',
    text,
)
if not secret_block:
    raise SystemExit('NEXUS_API_TOKEN declaration is missing')
body = secret_block.group('body')
if 'sync: false' not in body:
    raise SystemExit('NEXUS_API_TOKEN must be operator-supplied with sync: false')
if re.search(r'^\s*(value|generateValue):', body, re.M):
    raise SystemExit('NEXUS_API_TOKEN must not be materialized in render.yaml')

# The Stage D Blueprint must attach exactly one durable disk declaration to /data.
if text.count('mountPath: /data') != 1:
    raise SystemExit('Render Stage D must contain exactly one /data disk mount')

print('RENDER BLUEPRINT STATIC CONTRACT: PASS')
PY

render_sha="$(sha256sum render.yaml | awk '{print $1}')"
runbook_sha="$(sha256sum docs/RENDER-STAGE-D.md | awk '{print $1}')"
dockerfile_sha="$(sha256sum Dockerfile | awk '{print $1}')"

cat > render-deployment-manifest.txt <<EOF
Evidence Schema: NEXUS-RENDER-STAGE-D-CONFIG-v1
Status: PASS
Verified Commit: ${GITHUB_SHA}
Run ID: ${GITHUB_RUN_ID}
Provider Profile: Render paid single-instance web service
Persistent Mount: /data
Auto Deploy Gate: checksPass
Secret Material Recorded: NO
Authority Claim: NONE
Epistemic Claim: DEPLOYMENT-CONFIG-ONLY
Stage D Claim: NOT SATISFIED
Render Blueprint SHA-256: ${render_sha}
Render Stage D Runbook SHA-256: ${runbook_sha}
Deployment Dockerfile SHA-256: ${dockerfile_sha}
EOF

grep -Fx 'Status: PASS' render-deployment-manifest.txt
grep -Fx "Verified Commit: ${GITHUB_SHA}" render-deployment-manifest.txt
grep -Fx 'Secret Material Recorded: NO' render-deployment-manifest.txt
grep -Fx 'Authority Claim: NONE' render-deployment-manifest.txt
grep -Fx 'Epistemic Claim: DEPLOYMENT-CONFIG-ONLY' render-deployment-manifest.txt
grep -Fx 'Stage D Claim: NOT SATISFIED' render-deployment-manifest.txt

test "$(sha256sum render.yaml | awk '{print $1}')" = "$render_sha"
test "$(sha256sum docs/RENDER-STAGE-D.md | awk '{print $1}')" = "$runbook_sha"
test "$(sha256sum Dockerfile | awk '{print $1}')" = "$dockerfile_sha"

tar -czf render-deployment-bundle.tar.gz \
  render-deployment-manifest.txt \
  render.yaml \
  Dockerfile \
  docs/DEPLOYMENT.md \
  docs/STAGE-D-EVIDENCE.md \
  docs/RENDER-STAGE-D.md

test -s render-deployment-bundle.tar.gz
echo 'RENDER DEPLOYMENT CONFIG EVIDENCE: PASS'
