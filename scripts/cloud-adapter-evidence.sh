#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

: "${VERIFIED_COMMIT:?VERIFIED_COMMIT is required}"
: "${RUNNER_OS_NAME:?RUNNER_OS_NAME is required}"

[[ "$VERIFIED_COMMIT" =~ ^[0-9a-f]{40}$ ]] || {
  echo 'VERIFIED_COMMIT must be a full 40-character lowercase SHA' >&2
  exit 1
}

actual_commit="$(git rev-parse HEAD)"
if [[ "$actual_commit" != "$VERIFIED_COMMIT" ]]; then
  echo "checked-out commit does not match VERIFIED_COMMIT: ${actual_commit} != ${VERIFIED_COMMIT}" >&2
  exit 1
fi

(
  cd nexus-cloud
  uv sync --frozen
  uv run --frozen python -m compileall -q main.py tests
  uv run --frozen pytest -q
)
echo 'NEXUS CLOUD ADAPTER CONTRACT: PASS'

main_sha="$(sha256sum nexus-cloud/main.py | awk '{print $1}')"
tests_sha="$(find nexus-cloud/tests -type f -name '*.py' -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')"
pyproject_sha="$(sha256sum nexus-cloud/pyproject.toml | awk '{print $1}')"
lock_sha="$(sha256sum nexus-cloud/uv.lock | awk '{print $1}')"
contract_workflow_sha="$(sha256sum .github/workflows/cloud-adapter.yml | awk '{print $1}')"
evidence_workflow_sha="$(sha256sum .github/workflows/cloud-adapter-evidence.yml | awk '{print $1}')"
evidence_script_sha="$(sha256sum scripts/cloud-adapter-evidence.sh | awk '{print $1}')"
python_version="$(cd nexus-cloud && uv run --frozen python --version 2>&1)"
uv_version="$(uv --version)"

manifest='nexus-cloud-verification-manifest.txt'
printf '%s\n' \
  'Evidence Schema: NEXUS-CLOUD-TRANSPORT-v1' \
  'Status: PASS' \
  "Verified Commit: ${VERIFIED_COMMIT}" \
  "Runner OS: ${RUNNER_OS_NAME}" \
  "Python Version: ${python_version}" \
  "uv Version: ${uv_version}" \
  'Authority Claim: NONE' \
  'Epistemic Claim: TRANSPORT-CONTRACT-ONLY' \
  'Stage D Claim: NOT SATISFIED' \
  "Cloud main.py SHA-256: ${main_sha}" \
  "Cloud tests SHA-256: ${tests_sha}" \
  "Cloud pyproject.toml SHA-256: ${pyproject_sha}" \
  "Cloud uv.lock SHA-256: ${lock_sha}" \
  "Cloud contract workflow SHA-256: ${contract_workflow_sha}" \
  "Cloud evidence workflow SHA-256: ${evidence_workflow_sha}" \
  "Cloud evidence script SHA-256: ${evidence_script_sha}" \
  > "$manifest"

grep -Fx 'Evidence Schema: NEXUS-CLOUD-TRANSPORT-v1' "$manifest"
grep -Fx 'Status: PASS' "$manifest"
grep -Fx "Verified Commit: ${VERIFIED_COMMIT}" "$manifest"
grep -Fx 'Authority Claim: NONE' "$manifest"
grep -Fx 'Epistemic Claim: TRANSPORT-CONTRACT-ONLY' "$manifest"
grep -Fx 'Stage D Claim: NOT SATISFIED' "$manifest"
test "$(git rev-parse HEAD)" = "$VERIFIED_COMMIT"
test "$(sha256sum nexus-cloud/main.py | awk '{print $1}')" = "$main_sha"
test "$(find nexus-cloud/tests -type f -name '*.py' -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')" = "$tests_sha"
test "$(sha256sum nexus-cloud/pyproject.toml | awk '{print $1}')" = "$pyproject_sha"
test "$(sha256sum nexus-cloud/uv.lock | awk '{print $1}')" = "$lock_sha"
test "$(sha256sum .github/workflows/cloud-adapter.yml | awk '{print $1}')" = "$contract_workflow_sha"
test "$(sha256sum .github/workflows/cloud-adapter-evidence.yml | awk '{print $1}')" = "$evidence_workflow_sha"
test "$(sha256sum scripts/cloud-adapter-evidence.sh | awk '{print $1}')" = "$evidence_script_sha"
echo 'NEXUS CLOUD ADAPTER EVIDENCE SELF-AUDIT: PASS'

bundle='nexus-cloud-verification-bundle.tar.gz'
tar -czf "$bundle" \
  "$manifest" \
  nexus-cloud/main.py \
  nexus-cloud/tests \
  nexus-cloud/pyproject.toml \
  nexus-cloud/uv.lock \
  scripts/cloud-adapter-evidence.sh \
  .github/workflows/cloud-adapter.yml \
  .github/workflows/cloud-adapter-evidence.yml
sha256sum "$bundle" > nexus-cloud-verification-bundle.sha256

test -s "$bundle"
test -s nexus-cloud-verification-bundle.sha256
echo 'NEXUS CLOUD ADAPTER EVIDENCE BUNDLE: PASS'
