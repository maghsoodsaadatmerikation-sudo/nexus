#!/usr/bin/env bash
set -euo pipefail

required=(
  docs/V2.2-REVOCATION-REPLAY.md
  src/capability.rs
  Cargo.lock
)
for f in "${required[@]}"; do test -f "$f"; done

grep -Fq 'REVOCATION_SCHEMA_VERSION' src/capability.rs
grep -Fq 'RevocationSnapshot' src/capability.rs
grep -Fq 'RevocationReplayError' src/capability.rs
grep -Fq 'revocation_replay_reconstructs_state' src/capability.rs
grep -Fq 'repeated_revocation_remains_revoked_and_observable' src/capability.rs
grep -Fq 'broken_revocation_sequence_fails_closed' src/capability.rs
grep -Fq 'empty_revocation_identity_fails_closed' src/capability.rs
grep -Fq 'empty_revocation_provenance_fails_closed' src/capability.rs
grep -Fq 'No real verification -> no PASS -> no seal.' docs/V2.2-REVOCATION-REPLAY.md

# This gate verifies only the v2.2 revocation-replay boundary. Full formatting,
# locked build/test, type-boundary and lockfile integrity remain the responsibility
# of the independent canonical NEXUS Verification workflow and are re-bound by
# release-v2.2.yml before any seal can be created.
cargo test --locked capability::tests::revocation_replay_reconstructs_state
cargo test --locked capability::tests::repeated_revocation_remains_revoked_and_observable
cargo test --locked capability::tests::broken_revocation_sequence_fails_closed
cargo test --locked capability::tests::unsupported_revocation_schema_fails_closed
cargo test --locked capability::tests::empty_revocation_identity_fails_closed
cargo test --locked capability::tests::empty_revocation_provenance_fails_closed
cargo test --locked policy::tests::revoked_grant_never_constructs_authorized_request
cargo test --locked authority::tests::authority_cannot_increase

echo "NEXUS V2.2 REVOCATION REPLAY CHECK: PASS"
