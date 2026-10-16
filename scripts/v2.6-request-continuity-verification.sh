#!/usr/bin/env bash
# NEXUS v2.6 — Bounded Storage Failure & Request Continuity verification
# No real verification -> no PASS -> no seal.
set -euo pipefail

echo "=== NEXUS v2.6 Request Continuity Verification ==="

# 1. Static presence of release intent and contract docs
test -f release-intents/v2.6.0
test -f release-intents/v2.6.0.request
test -f docs/V2.6-BOUNDED-STORAGE-FAILURE.md

# 2. RequestStore source must retain reserve-before-delegate and Indeterminate recovery
grep -q 'file.write_all(b"p")' artifact-05/src/request_store.rs
grep -q 'file.sync_all()' artifact-05/src/request_store.rs
grep -q 'RequestStatus::Indeterminate' artifact-05/src/request_store.rs
grep -q 'killed_writer_recovers_reservation_as_indeterminate' artifact-05/src/request_store.rs

# 3. Run locked unit tests that exercise the continuity contract
cargo test --manifest-path artifact-05/Cargo.toml --locked request_store -- --nocapture

echo "=== v2.6 verification script completed (unit tests passed) ==="
