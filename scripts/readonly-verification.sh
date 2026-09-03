#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

: "${RUST_IMAGE:?RUST_IMAGE is required}"
: "${GITHUB_SHA:?GITHUB_SHA is required}"
: "${GITHUB_RUN_ID:?GITHUB_RUN_ID is required}"

RUNNER_TEMP="${RUNNER_TEMP:-/tmp}"
GITHUB_WORKSPACE="${GITHUB_WORKSPACE:-$ROOT}"
RUNNER_OS="${RUNNER_OS:-unknown}"

[[ "$GITHUB_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo 'GITHUB_SHA must be a full 40-character lowercase SHA' >&2
  exit 1
}

actual_commit="$(git rev-parse HEAD)"
if [[ "$actual_commit" != "$GITHUB_SHA" ]]; then
  echo "checked-out commit does not match GITHUB_SHA: ${actual_commit} != ${GITHUB_SHA}" >&2
  exit 1
fi

case "$RUST_IMAGE" in
  rust@sha256:????????????????????????????????????????????????????????????????) ;;
  *) echo 'RUST_IMAGE must be digest-pinned' >&2; exit 1 ;;
esac

# Static and fail-closed release checks.
python3 scripts/verify_test_matrix.py
bash -n scripts/workspace-backup.sh
bash -n scripts/workspace-restore.sh
bash -n scripts/stage-d-evidence.sh
bash -n scripts/v1.1-release-readiness.sh
bash -n scripts/v1.1-release-candidate.sh
bash -n scripts/verify-docker.sh
bash -n scripts/verify-manifest.sh
bash -n scripts/readonly-verification.sh

incomplete="$RUNNER_TEMP/stage-d-incomplete-${GITHUB_RUN_ID}"
rm -rf "$incomplete"
mkdir -p "$incomplete"
if bash scripts/v1.1-release-readiness.sh "$incomplete" "$GITHUB_SHA" >"$RUNNER_TEMP/readiness-${GITHUB_RUN_ID}.out" 2>"$RUNNER_TEMP/readiness-${GITHUB_RUN_ID}.err"; then
  echo 'release-readiness gate incorrectly accepted incomplete Stage D evidence' >&2
  exit 1
fi
grep -F 'V1.1 RELEASE READINESS: BLOCKED' "$RUNNER_TEMP/readiness-${GITHUB_RUN_ID}.err" >/dev/null
if bash scripts/v1.1-release-candidate.sh "$incomplete" "$GITHUB_SHA" "$GITHUB_RUN_ID" >"$RUNNER_TEMP/candidate-${GITHUB_RUN_ID}.out" 2>"$RUNNER_TEMP/candidate-${GITHUB_RUN_ID}.err"; then
  echo 'release-candidate gate incorrectly accepted incomplete Stage D evidence' >&2
  exit 1
fi
grep -F 'V1.1 RELEASE CANDIDATE: BLOCKED' "$RUNNER_TEMP/candidate-${GITHUB_RUN_ID}.err" >/dev/null
echo 'V1.1 RELEASE READINESS FAIL-CLOSED: PASS'
echo 'V1.1 RELEASE CANDIDATE FAIL-CLOSED: PASS'

# Constitutional core verification. This produces only local evidence files;
# it does not publish, attest, authorize, or mutate repository state.
RUST_IMAGE="$RUST_IMAGE" \
GITHUB_SHA="$GITHUB_SHA" \
GITHUB_RUN_ID="$GITHUB_RUN_ID" \
RUNNER_OS="$RUNNER_OS" \
  bash scripts/verify-docker.sh

GITHUB_SHA="$GITHUB_SHA" \
GITHUB_RUN_ID="$GITHUB_RUN_ID" \
  bash scripts/verify-manifest.sh verification-manifest.txt "build_verification_${GITHUB_RUN_ID}.log"

tar -czf verification-bundle.tar.gz \
  verification-manifest.txt \
  "build_verification_${GITHUB_RUN_ID}.log" \
  Cargo.lock

test -s verification-bundle.tar.gz

# Artifact 05 gates.
docker pull "$RUST_IMAGE"
test -f artifact-05/Cargo.toml
test -f artifact-05/Cargo.lock
test -f web/index.html
echo 'GATE 0 PASS'

docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$GITHUB_WORKSPACE:/workspace" \
  -w /workspace/artifact-05 \
  "$RUST_IMAGE" \
  sh -euxc 'cargo fmt -- --check; cargo build --locked'
echo 'GATE 1 PASS'

docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$GITHUB_WORKSPACE:/workspace" \
  -w /workspace/artifact-05 \
  "$RUST_IMAGE" \
  sh -euxc 'cargo test --locked; cargo test --doc --locked'
echo 'GATE 2 PASS'

# Deployment smoke, persistence and recovery checks on an isolated local mount.
smoke_data="$RUNNER_TEMP/nexus-smoke-data-${GITHUB_RUN_ID}"
backup="$RUNNER_TEMP/ci-smoke-backup-${GITHUB_RUN_ID}.json"
restored="$RUNNER_TEMP/ci-smoke-restored-${GITHUB_RUN_ID}.json"
container="nexus-smoke-${GITHUB_RUN_ID}"
port="$((18080 + (GITHUB_RUN_ID % 1000)))"
mkdir -p "$smoke_data"
chmod 0777 "$smoke_data"

cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
}

wait_healthy() {
  for _ in $(seq 1 30); do
    health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "$container")"
    case "$health" in
      healthy) return 0 ;;
      unhealthy|missing)
        docker inspect "$container"
        docker logs "$container" || true
        return 1
        ;;
    esac
    sleep 1
  done
  docker inspect "$container"
  docker logs "$container" || true
  return 1
}

start_container() {
  docker run -d --name "$container" \
    -p "127.0.0.1:${port}:3000" \
    -e NEXUS_API_TOKEN=ci-smoke-token \
    -v "$smoke_data:/data" \
    nexus-ci-smoke
  wait_healthy
}

assert_redacted_startup() {
  logs="$(docker logs "$container" 2>&1)"
  printf '%s\n' "$logs" | grep -F 'NEXUS_OP event=startup bind_addr=0.0.0.0:3000 data_dir=/data auth=configured'
  if printf '%s\n' "$logs" | grep -F 'ci-smoke-token'; then
    echo 'secret leaked into application logs' >&2
    return 1
  fi
}

trap cleanup EXIT
docker build --pull=false -t nexus-ci-smoke .
start_container
assert_redacted_startup
curl -fsS "http://127.0.0.1:${port}/" >/dev/null
curl -fsS -X POST "http://127.0.0.1:${port}/v1/workspaces" \
  -H 'content-type: application/json' \
  -H 'authorization: Bearer ci-smoke-token' \
  --data '{"workspace_id":"ci-smoke","question":"backup recovery and persistence smoke","provenance_id":"ci:smoke"}' \
  >/dev/null
NEXUS_BASE_URL="http://127.0.0.1:${port}" \
NEXUS_API_TOKEN=ci-smoke-token \
NEXUS_WORKSPACE_ID=ci-smoke \
  bash scripts/workspace-backup.sh "$backup"
cleanup
find "$smoke_data" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
start_container
assert_redacted_startup
NEXUS_BASE_URL="http://127.0.0.1:${port}" \
NEXUS_API_TOKEN=ci-smoke-token \
  bash scripts/workspace-restore.sh "$backup" >/dev/null
curl -fsS \
  -H 'authorization: Bearer ci-smoke-token' \
  "http://127.0.0.1:${port}/v1/workspaces/ci-smoke" \
  > "$restored"
python3 -c 'import json,sys; assert json.load(open(sys.argv[1])) == json.load(open(sys.argv[2]))' "$backup" "$restored"
cleanup
start_container
assert_redacted_startup
curl -fsS -H 'authorization: Bearer ci-smoke-token' "http://127.0.0.1:${port}/v1/workspaces/ci-smoke" >/dev/null
echo 'DEPLOYMENT HEALTH PASS'
echo 'BACKUP RECOVERY PASS'
echo 'OPERATIONAL OBSERVABILITY PASS'
echo 'DEPLOYMENT SMOKE PASS'

# Artifact 05 evidence manifest and local bundle.
lock_sha="$(sha256sum artifact-05/Cargo.lock | awk '{print $1}')"
toml_sha="$(sha256sum artifact-05/Cargo.toml | awk '{print $1}')"
source_sha="$(find artifact-05/src artifact-05/tests -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')"
web_sha="$(sha256sum web/index.html | awk '{print $1}')"
dockerfile_sha="$(sha256sum Dockerfile | awk '{print $1}')"
backup_script_sha="$(sha256sum scripts/workspace-backup.sh | awk '{print $1}')"
restore_script_sha="$(sha256sum scripts/workspace-restore.sh | awk '{print $1}')"
stage_d_script_sha="$(sha256sum scripts/stage-d-evidence.sh | awk '{print $1}')"
readiness_script_sha="$(sha256sum scripts/v1.1-release-readiness.sh | awk '{print $1}')"
candidate_script_sha="$(sha256sum scripts/v1.1-release-candidate.sh | awk '{print $1}')"
readonly_script_sha="$(sha256sum scripts/readonly-verification.sh | awk '{print $1}')"
stage_d_doc_sha="$(sha256sum docs/STAGE-D-EVIDENCE.md | awk '{print $1}')"
readiness_doc_sha="$(sha256sum docs/RELEASE-READINESS-v1.1.md | awk '{print $1}')"
candidate_doc_sha="$(sha256sum docs/RELEASE-CANDIDATE-v1.1.md | awk '{print $1}')"
observability_sha="$(sha256sum docs/OBSERVABILITY.md | awk '{print $1}')"

cat > artifact-05-verification-manifest.txt <<EOF
Status: PASS
Verified Commit: ${GITHUB_SHA}
Run ID: ${GITHUB_RUN_ID}
Docker Reference: ${RUST_IMAGE}
Authority Claim: NONE
Epistemic Claim: VERIFICATION-ONLY
GATE 0: PASS
GATE 1: PASS
GATE 2: PASS
Deployment Health: PASS
Backup Recovery: PASS
Operational Observability: PASS
Deployment Smoke: PASS
V1.1 Release Readiness Fail-Closed: PASS
V1.1 Release Candidate Fail-Closed: PASS
Artifact 05 Cargo.lock SHA-256: ${lock_sha}
Artifact 05 Cargo.toml SHA-256: ${toml_sha}
Artifact 05 Source Tree SHA-256: ${source_sha}
Web Workspace SHA-256: ${web_sha}
Deployment Dockerfile SHA-256: ${dockerfile_sha}
Workspace Backup Script SHA-256: ${backup_script_sha}
Workspace Restore Script SHA-256: ${restore_script_sha}
Stage D Evidence Script SHA-256: ${stage_d_script_sha}
V1.1 Release Readiness Script SHA-256: ${readiness_script_sha}
V1.1 Release Candidate Script SHA-256: ${candidate_script_sha}
Read-Only Verification Script SHA-256: ${readonly_script_sha}
Stage D Evidence Contract SHA-256: ${stage_d_doc_sha}
V1.1 Release Readiness Contract SHA-256: ${readiness_doc_sha}
V1.1 Release Candidate Contract SHA-256: ${candidate_doc_sha}
Observability Contract SHA-256: ${observability_sha}
EOF

grep -Fx 'Status: PASS' artifact-05-verification-manifest.txt
grep -Fx "Verified Commit: ${GITHUB_SHA}" artifact-05-verification-manifest.txt
grep -Fx "Docker Reference: ${RUST_IMAGE}" artifact-05-verification-manifest.txt
grep -Fx 'Authority Claim: NONE' artifact-05-verification-manifest.txt
grep -Fx 'Epistemic Claim: VERIFICATION-ONLY' artifact-05-verification-manifest.txt
grep -Fx 'Deployment Health: PASS' artifact-05-verification-manifest.txt
grep -Fx 'Backup Recovery: PASS' artifact-05-verification-manifest.txt
grep -Fx 'Operational Observability: PASS' artifact-05-verification-manifest.txt
grep -Fx 'Deployment Smoke: PASS' artifact-05-verification-manifest.txt
grep -Fx 'V1.1 Release Readiness Fail-Closed: PASS' artifact-05-verification-manifest.txt
grep -Fx 'V1.1 Release Candidate Fail-Closed: PASS' artifact-05-verification-manifest.txt

test "$(git rev-parse HEAD)" = "$GITHUB_SHA"
test "$(sha256sum artifact-05/Cargo.lock | awk '{print $1}')" = "$lock_sha"
test "$(sha256sum artifact-05/Cargo.toml | awk '{print $1}')" = "$toml_sha"
test "$(find artifact-05/src artifact-05/tests -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')" = "$source_sha"
test "$(sha256sum web/index.html | awk '{print $1}')" = "$web_sha"
test "$(sha256sum Dockerfile | awk '{print $1}')" = "$dockerfile_sha"
test "$(sha256sum scripts/workspace-backup.sh | awk '{print $1}')" = "$backup_script_sha"
test "$(sha256sum scripts/workspace-restore.sh | awk '{print $1}')" = "$restore_script_sha"
test "$(sha256sum scripts/stage-d-evidence.sh | awk '{print $1}')" = "$stage_d_script_sha"
test "$(sha256sum scripts/v1.1-release-readiness.sh | awk '{print $1}')" = "$readiness_script_sha"
test "$(sha256sum scripts/v1.1-release-candidate.sh | awk '{print $1}')" = "$candidate_script_sha"
test "$(sha256sum scripts/readonly-verification.sh | awk '{print $1}')" = "$readonly_script_sha"
test "$(sha256sum docs/STAGE-D-EVIDENCE.md | awk '{print $1}')" = "$stage_d_doc_sha"
test "$(sha256sum docs/RELEASE-READINESS-v1.1.md | awk '{print $1}')" = "$readiness_doc_sha"
test "$(sha256sum docs/RELEASE-CANDIDATE-v1.1.md | awk '{print $1}')" = "$candidate_doc_sha"
test "$(sha256sum docs/OBSERVABILITY.md | awk '{print $1}')" = "$observability_sha"
echo 'GATE 3 PASS'

tar -czf artifact-05-verification-bundle.tar.gz \
  artifact-05-verification-manifest.txt \
  artifact-05/Cargo.toml \
  artifact-05/Cargo.lock \
  artifact-05/src \
  artifact-05/tests \
  web/index.html \
  Dockerfile \
  .dockerignore \
  scripts/workspace-backup.sh \
  scripts/workspace-restore.sh \
  scripts/stage-d-evidence.sh \
  scripts/v1.1-release-readiness.sh \
  scripts/v1.1-release-candidate.sh \
  scripts/readonly-verification.sh \
  docs/DEPLOYMENT.md \
  docs/OBSERVABILITY.md \
  docs/STAGE-D-EVIDENCE.md \
  docs/RELEASE-READINESS-v1.1.md \
  docs/RELEASE-CANDIDATE-v1.1.md \
  docs/ROADMAP-v1.1.md

test -s artifact-05-verification-bundle.tar.gz
cleanup
trap - EXIT

echo 'NEXUS READ-ONLY VERIFICATION: PASS'
