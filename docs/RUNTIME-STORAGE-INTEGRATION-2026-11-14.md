# Operational integration: request ledger + pinned workspaces

Date: 2026-11-14
Branch: `integration/runtime-storage-readiness-199-200-20261114`
Base: `b7855b1a1bb9f3776e8f24b682d124cbe334543e`
Authority: **unmerged draft, no release/deployment/attestation**

## Provenance of the two prior passing repairs

The following exact Git blobs were copied from the **verified** source heads
before extending them in this integration:

- PR #199 (`27c2efefeabb6ca8f8feb009e398a94ab0d18b88`):
  - `artifact-05/src/lib.rs` — `e4a58827725c8971a75824e56b73eecc568a3681`
  - `artifact-05/src/request_store.rs` — `e988175dfeccaab1b2adfda0af096541647d7302`
  - `artifact-05/tests/http_contract.rs` — `a52ab2b2868569d27322b0e18eb04cc4213b65c5`
  - `docs/RUNTIME-STORAGE-READINESS-2026-11-14.md` — `654a1bf53d0de90e8ef33d4c10d55fba14c847dc`
  - `docs/gateway-health.md` — `e913880ec94df5e3f537d74f42009e831a43e97f`
  - `scripts/verify-storage-failure-http.py` — `7d51a52eadafdc4f9aee3eed549c14b85f562e6b`
- PR #200 (`8fffb40a22ea4c6ef19fbc3e5136b89b399422c3`):
  - `artifact-05/src/main.rs` — `b5bdd217a3807a411c4c2e9fce6b708e91ee5f06`
  - `docs/WORKSPACE-RUNTIME-ROOT-IDENTITY-2026-11-14.md` — `5ecf5da74f847601ce8082991e12fb650ce36b4e`
  - `src/workspace_persistence.rs` — `e3e76970656ead0cb76a675d18674cefff68ac06`

These repairs had disjoint source paths, avoiding conflict. The integration
then adds an explicit workspace-health interface, runtime HTTP coverage and
correct storage-error classification. The final modified Git blob IDs
necessarily differ from source identities; do not treat this document as a
cryptographic validation of runtime behavior.

## Newly addressed operational defects

1. **False green workspace readiness:** Even with the request ledger readable,
   the gateway could claim ready without checking its pinned workspace store.
   Production `CoreDelegate` now checks the configured workspace directory
   identity through a distinct cloned pinned repository handle. The health
   check does not take the writer mutex, mutate snapshots or clear quarantine.
   `GET /readyz` returns 503 `workspace_unavailable` for a failed
   workspace probe; liveness remains 200.
2. **Storage outage mislabeled as invalid client input:** The real binary
   previously mapped all durable read/write errors to
   `WorkspaceDelegateError::Invalid`, yielding HTTP 422 even for storage
   `Io` failures. It now maps `DurableWorkspaceError::Io` to distinct
   `StorageUnavailable` and HTTP 503
   `workspace_storage_unavailable`. Schema, audit and other
   validation failures retain their HTTP 422 classification.
3. **Fragmented readiness fixes:** Consolidates the previously tested request
   ledger 503 `storage_unavailable` and permanent admission capacity 503
   `admission_unavailable` with workspace storage checks.

## Required evidence

- All GitHub CI jobs on the **exact integration head** must succeed.
- The mandatory `readonly-verification` must include cargo fmt, Rust
  unit/integration tests, durable-state recovery, and real HTTP synthetic
  missing-ledger recovery checks.
- The new binary-level Rust HTTP test must prove 200 before/after exact inode
  restoration, 503 during root replacement for both readiness and workspace
  reads/writes, and no files written into a substitute directory.
- Cloud tests are not evidence of the separate live Render service.

## Self-critique and release hold

Workspace readiness is a bounded-by-work design but it performs synchronous
kernel metadata calls on the request path. Slow or stalled remote filesystem
operations can still block; these tests do **not** prove a latency bound.
Read-only metadata can succeed while a future write fails due to ENOSPC,
permission changes or an I/O race. A 503 does not itself authorize clearing
a restoration quarantine. The gateway does not claim total workspace data
integrity, independent full-data recovery or production availability.

Do not merge this draft into `main` or deploy until independent provider-side
off-host restore evidence, Render auto-deploy control, and strict up-to-date
GitHub branch status checks are verified. Prior PRs #199/#200 remain unmerged;
they are source inputs, not production release proof. A full reconciliation
with pending Rust feature stack #129–#134 is required before feature merges.
