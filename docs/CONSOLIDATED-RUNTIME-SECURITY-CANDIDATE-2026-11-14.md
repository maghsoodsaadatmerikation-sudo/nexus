# NEXUS consolidated runtime and cloud-security candidate
Date: 2026-11-14
Status: **UNMERGED DRAFT — REVIEW ONLY — NO RELEASE AUTHORITY**
Pinned base main: `b7855b1a1bb9f3776e8f24b682d124cbe334543e`

## Independently tested source inputs
- PR #197, commit `7f8b0703ef74c02b71290af9556a080dd90c90aa`: Studio JSON duplicate-key and provider-boundary hardening; Cloud-to-core duplicate auth/HTTP framing header rejection; Python regressions and required PR cloud tests.
- PR #198, commit `4e95bfc1ed0c70ebdcb37a7330106c1434753e36`: Rust gateway rejects multiple Authorization headers and invalid configured tokens; exact-bearer regressions.
- PR #202, commit `a000aafa7e14e4dfee391639526c0df98cd75128`, already containing the tested #201/#199/#200 lineage: runtime /readyz storage and capacity reporting, pinned workspace roots, workspace 503 error classification, atomic create/import with cross-process lock, fault-injection tests.

## Composition strategy
The seven original Cloud/Studio source and documentation blobs from #197
were copied exactly (excluding its standalone integration provenance workflow,
manifest, and check script, which **only accepts a 197-only source delta**).
The mandatory `readonly-verification` GitHub workflow was retained from
#197 and extended to call
`scripts/verify-composed-security-source.py`. This new gate verifies 13
known exact inherited Git blob identities and rejects missing or modified
provenance-controlled files. Its assertions over manually merged Rust
functions are structural smoke checks only; full behavior is tested via
Cargo and HTTP regressions. Do not treat Git SHA-1 object IDs as signatures.

`artifact-05/src/lib.rs` and `artifact-05/tests/http_contract.rs` overlapped
between #198 and #202: Rust header-cardinality and startup token checks
were merged into the inherited runtime readiness implementation, and the
three source-auth tests appended without losing the durable-ledger or
admission-capacity tests. These two modified files **are not claimed to
retain either original blob SHA**; the composed HEAD and exact CI results
are the evidence of integration.

## Required before calling this a passing engineering candidate
1. Exact-current-head **all** GitHub checks succeed, especially mandatory
   `readonly-verification` containing mandatory Python cloud tests, the
   13-blob composed provenance gate, Cargo fmt/build/tests and full
   synthetic HTTP missing-ledger/restart recovery.
2. Auth tests reject ambiguous duplicate Bearer headers while still
   accepting an exact single credential.
3. Workspace isolation, atomic create/import and startup/runtime health
   tests remain green with no loss of safety gates.
4. Fresh commit and required check identities must be checked again
   after any final change.

## Open operational blockers — NOT FIXED BY THIS CANDIDATE
- Main ruleset `Merikation` (ID `20870033`) still has
  `strict_required_status_checks_policy=false`; stale required green checks
  may be considered sufficient after the base moves. An authorized GitHub
  administrator must require a fresh base/current checks.
- Render service `nexus` is set to auto-deploy `main`. Merging this PR
  could alter live code without an approved provider-side deployment plan.
- A full independent offsite backup-and-restore witness on the real
  provider, destructive restore rehearsal and independent attestation
  remain unverified. CI's synthetic restore is not that proof.
- Outstanding #129–#134 feature-stack edits to the Rust workspace
  repository are not incorporated here. Reconcile them separately before
  merging feature work; do not accidentally overwrite this source.
- Filesystem readiness cannot prove ENOSPC-free future fsync, remote
  distributed lock correctness or zero-latency kernel I/O.

This PR stays **draft**. No production secrets, user data, Render settings,
`main`, stage seal or release tags were changed.
