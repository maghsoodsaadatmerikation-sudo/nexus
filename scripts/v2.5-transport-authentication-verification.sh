#!/usr/bin/env bash
set -euo pipefail

test -f Cargo.lock
test -f artifact-05/Cargo.lock
test -f artifact-05/Cargo.toml
test -f artifact-05/CONTRACT.md
test -f artifact-05/src/lib.rs
test -f artifact-05/src/workspace_api.rs
test -f artifact-05/tests/http_contract.rs
test -f docs/V2.5-UNIFIED-TRANSPORT-AUTHENTICATION.md

grep -Fq 'transport_authorized' artifact-05/src/lib.rs
grep -Fq 'transport_authentication_required' artifact-05/src/lib.rs
grep -Fq 'authenticated_request_routes_reject_before_parse_lookup_or_delegation' artifact-05/tests/http_contract.rs
grep -Fq 'return 401 before JSON parsing, delegate invocation, or status lookup' artifact-05/CONTRACT.md
grep -Fq 'A_out <= A_in' docs/V2.5-UNIFIED-TRANSPORT-AUTHENTICATION.md

# Verify observable boundaries independently of the JSON extractor implementation.
# Exact names plus result-count checks prevent a renamed/missing test from passing
# vacuously (cargo otherwise succeeds when a filter selects zero tests).
verification_log="$(mktemp)"
trap 'rm -f "$verification_log"' EXIT
for boundary_test in \
  authenticated_request_routes_reject_before_parse_lookup_or_delegation \
  unknown_and_authority_like_fields_fail_closed_before_delegation \
  artifact_07_authentication_precedes_safety_budget_consumption
do
  cargo test --manifest-path artifact-05/Cargo.toml --locked \
    --test http_contract "$boundary_test" -- --exact --nocapture \
    2>&1 | tee "$verification_log"
  grep -Fq "test $boundary_test ... ok" "$verification_log"
  grep -Fq 'test result: ok. 1 passed; 0 failed;' "$verification_log"
done

cargo test --manifest-path artifact-05/Cargo.toml --locked
echo 'V2.5 TRANSPORT AUTHENTICATION BEHAVIOR: PASS'
