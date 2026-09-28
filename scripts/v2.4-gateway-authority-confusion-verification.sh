#!/usr/bin/env bash
set -euo pipefail

test -f Cargo.lock
test -f artifact-05/Cargo.toml
test -f artifact-05/CONTRACT.md
test -f artifact-05/src/lib.rs
test -f artifact-05/tests/http_contract.rs
test -f docs/V2.4-GATEWAY-AUTHORITY-CONFUSION.md

grep -Fq 'deny_unknown_fields' artifact-05/src/lib.rs
grep -Fq 'unknown_and_authority_like_fields_fail_closed_before_delegation' artifact-05/tests/http_contract.rs
grep -Fq 'gateway_exposes_no_capability_or_policy_mutation_routes' artifact-05/tests/http_contract.rs
grep -Fq 'unknown fields are rejected with `422` before delegation' artifact-05/CONTRACT.md
grep -Fq 'A_out <= A_in' docs/V2.4-GATEWAY-AUTHORITY-CONFUSION.md

cargo test --manifest-path artifact-05/Cargo.toml --locked
