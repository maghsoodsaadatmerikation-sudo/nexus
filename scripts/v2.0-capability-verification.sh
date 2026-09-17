#!/usr/bin/env bash
set -euo pipefail

test -f src/capability.rs
test -f docs/V2-CAPABILITY-DELEGATION.md
grep -Fq 'A_child <= A_parent <= A_in' docs/V2-CAPABILITY-DELEGATION.md
grep -Fq 'pub mod capability;' src/lib.rs

cargo test --locked capability::tests::
cargo test --locked authority::tests::authority_cannot_increase
cargo test --locked tests::authorized_flow_is_deterministic

echo 'NEXUS V2 CAPABILITY VERIFICATION: PASS'
