#!/usr/bin/env bash
# Read-only engineering witness, using disposable process/tmpfs state only.
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_root"
readonly rust_image='rust@sha256:0ff31c9ffa641a62e48d543fb00b4960955ea375f40776f40f585b89e654cc5e'
witness_dir="$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/nexus-continuity.XXXXXX")"
trap 'rm -rf -- "$witness_dir"' EXIT

# --exact can silently run zero tests after a rename. Require the named witness
# and its one-test success summary, with pipefail preserving cargo failures.
docker run --rm --user "$(id -u):$(id -g)" \
  -v "$repo_root:/workspace" -w /workspace "$rust_image" \
  cargo test --manifest-path artifact-05/Cargo.toml --locked --lib \
  request_store::tests::killed_writer_recovers_reservation_as_indeterminate \
  -- --exact --nocapture 2>&1 | tee "$witness_dir/crash.log"
grep -Fq 'test request_store::tests::killed_writer_recovers_reservation_as_indeterminate ... ok' "$witness_dir/crash.log"
grep -Fq 'test result: ok. 1 passed; 0 failed; 0 ignored;' "$witness_dir/crash.log"
echo 'REQUEST CONTINUITY PROCESS CRASH: PASS'

# The ignored test must execute on a kernel-bounded private mount. Never attach
# a provider volume, host data directory or network filesystem to this witness.
docker run --rm --user "$(id -u):$(id -g)" \
  --tmpfs /tmp/nexus-test-enospc:rw,size=8m,mode=0777 \
  -v "$repo_root:/workspace" -w /workspace "$rust_image" \
  cargo test --manifest-path artifact-05/Cargo.toml --locked --test http_contract \
  enospc_reservation_fails_before_delegation -- --ignored --exact --nocapture \
  2>&1 | tee "$witness_dir/enospc.log"
grep -Fq 'test enospc_reservation_fails_before_delegation ... ok' "$witness_dir/enospc.log"
grep -Fq 'test result: ok. 1 passed; 0 failed; 0 ignored;' "$witness_dir/enospc.log"
echo 'REQUEST CONTINUITY BOUNDED ENOSPC: PASS'
echo 'NEXUS REQUEST CONTINUITY: PASS (synthetic engineering evidence; authority=none; unsealed)'
