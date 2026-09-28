#!/usr/bin/env bash
set -euo pipefail

test -f Cargo.lock
test -f src/authorized.rs
test -f src/capability.rs
test -f src/executor.rs
test -f docs/V2.3-REVOCATION-FRESHNESS.md

grep -Fq 'pub struct DelegatedAuthorizedRequest' src/authorized.rs
grep -Fq 'pub fn revocation_epoch(&self) -> u64' src/authorized.rs
grep -Fq 'pub fn epoch(&self) -> u64' src/capability.rs
grep -Fq 'pub fn execute_delegated' src/executor.rs
grep -Fq 'StaleRevocationEpoch' src/executor.rs
grep -Fq 'revocation_after_authorization_rejects_stale_request' src/executor.rs
grep -Fq 'unrelated_revocation_invalidates_cached_authorization' src/executor.rs
grep -Fq 'older_snapshot_cannot_execute_newer_authorization' src/executor.rs
grep -Fq 'equal_epoch_divergent_history_fails_closed' src/executor.rs
grep -Fq 'reauthorization_at_current_epoch_restores_only_unrevoked_request' src/executor.rs

cargo test --locked executor::delegated_freshness_tests
cargo test --locked capability::tests::revocation_epoch_is_reconstructed_from_valid_history
