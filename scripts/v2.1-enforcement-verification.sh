#!/usr/bin/env bash
set -euo pipefail

required=(
  src/capability.rs
  src/lib.rs
  docs/V2-CAPABILITY-DELEGATION.md
  scripts/run_gates.sh
  scripts/verify-docker.sh
)
for f in "${required[@]}"; do test -f "$f" || { echo "missing:$f"; exit 1; }; done

# v2.1 validity/audit boundary must exist.
grep -Fq 'InvalidValidityWindow' src/capability.rs
grep -Fq 'CapabilityAuditLog' src/capability.rs
grep -Fq 'CapabilityAuditEvent' src/capability.rs

# Required negative and boundary tests must be present; canonical NEXUS Verification executes them locked.
for test_name in \
  zero_length_validity_window_fails_closed \
  inverted_validity_window_fails_closed \
  audit_is_append_only_from_public_api; do
  grep -Fq "$test_name" src/capability.rs || { echo "missing-test:$test_name"; exit 1; }
done

# Canonical verification remains the executable authority for the Rust suite.
grep -Fq 'cargo test --locked' scripts/run_gates.sh
grep -Fq 'Verification Mode: locked' scripts/verify-docker.sh

echo 'NEXUS V2.1 ENFORCEMENT CONTRACT CHECK: PASS'
