#!/usr/bin/env bash
set -euo pipefail

test -f Cargo.lock
test -f artifact-05/Cargo.toml
test -f artifact-05/CONTRACT.md
test -f artifact-05/src/lib.rs
test -f artifact-05/src/workspace_api.rs
test -f artifact-05/tests/http_contract.rs
test -f docs/V2.5-UNIFIED-TRANSPORT-AUTHENTICATION.md

grep -Fq 'transport_authorized' artifact-05/src/lib.rs
grep -Fq 'transport_authentication_required' artifact-05/src/lib.rs
grep -Fq 'Json::<SubmitRequest>::from_request' artifact-05/src/lib.rs
grep -Fq 'authenticated_request_routes_reject_before_parse_lookup_or_delegation' artifact-05/tests/http_contract.rs
grep -Fq 'return 401 before JSON parsing, delegate invocation, or status lookup' artifact-05/CONTRACT.md
grep -Fq 'A_out <= A_in' docs/V2.5-UNIFIED-TRANSPORT-AUTHENTICATION.md

cargo test --manifest-path artifact-05/Cargo.toml --locked
