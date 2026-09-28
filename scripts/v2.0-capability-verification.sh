#!/usr/bin/env bash
set -euo pipefail

test -f src/capability.rs
test -f docs/V2-CAPABILITY-DELEGATION.md
grep -Fq 'A_child <= A_parent <= A_in' docs/V2-CAPABILITY-DELEGATION.md
grep -Fq 'pub mod capability;' src/lib.rs

# The canonical NEXUS Verification workflow executes the full locked Rust test
# suite in the digest-pinned verification image. This v2-specific gate checks
# that every required fail-closed test is present; the release gate separately
# requires canonical NEXUS Verification SUCCESS for this exact commit.
for test_name in \
  bounded_grant_is_valid \
  amplification_fails_closed \
  cross_scope_fails_closed \
  expiry_is_exclusive \
  pre_issuance_fails_closed \
  revocation_is_monotonic \
  subject_mismatch_fails_closed \
  unsupported_schema_fails_closed \
  empty_scope_fails_closed
do
  grep -Fq "fn ${test_name}()" src/capability.rs
 done

grep -Fq 'cargo test --locked' scripts/run_gates.sh
grep -Fq 'Verification Mode: locked' scripts/verify-docker.sh

echo 'NEXUS V2 CAPABILITY CONTRACT CHECK: PASS'
