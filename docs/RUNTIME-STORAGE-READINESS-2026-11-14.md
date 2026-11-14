# Runtime operational defect: false-green request-ledger readiness

Date: 2026-11-14
Base: `b7855b1a1bb9f3776e8f24b682d124cbe334543e`
Scope: **draft source code and synthetic CI only**

## Verified defect in the existing code

Before this candidate, the Rust `/readyz` route returned 200 whenever the
startup-latched recovery quarantine was absent. The durable request ledger
may subsequently be removed, moved, or replaced while the gateway continues
to run. In that state, `POST /v1/requests` rejects with 503
`request_store_unavailable`, yet `GET /readyz` returned 200 `ready`.

This is a direct operational false-green. An external router or monitoring
system relying on readiness could continue directing new requests to an
instance that cannot persist the reservation before execution.

## Minimal repair

- Add `RequestStore::check_readiness()`: verify that the configured
  filesystem path still resolves to the *same inode* as the pinned open
  ledger descriptor, ensure its directory can be opened and an entry
  enumerated, and verify identity again. The probe does not write.
- Return public, generic 503 `{"status":"storage_unavailable"}` when that
  probe fails. Continue to prioritize 503 `quarantined` on the latched
  recovery gate; retain 200 `alive` on `/livez` so recoverable storage
  outages cannot trigger unnecessary Docker restart loops.
- Retain 200 `ready` when the original ledger path is restored. A
  replacement directory or even a symlink to the original moved directory
  remains not ready.
- Assert these states with an in-process Rust router regression, as well as
  the real HTTP listener's existing synthetic fault-injection witness. The
  latter moves only CI's disposable mounted ledger, not production files.

## Boundaries and self-critique

This checks the request ledger, **not** total filesystem writability,
ENOSPC, free space, workspace-store health, model availability, or Rust
executor capacity. It is not a health attestation, independent backup
witness, or permission to resume quarantined storage. Even a successful
read-only probe can race with a later storage failure; the reserve path
still fails closed. Filesystem metadata calls are not intrinsically
time-bounded on all remote filesystems, and no broad distributed
availability claim is made here.

Draft only. No merge to `main` until Render auto-deploy is controlled,
independent recovery evidence exists, and the main branch ruleset requires
fresh status checks. Existing feature PR #130 also changes
`artifact-05/src/lib.rs`, so reconcile that overlap before integration.

## Required evidence

- GitHub `readonly-verification` must pass on the exact head including
  Cargo format, Rust and gateway tests and real HTTP missing-ledger fault.
- Other workflow tests on the head must not fail.
- Full offsite restore and provider-side deployment proof remain separate.

## Second operational false-ready detected during self-review

The gateway also reported 200 `ready` after its configured
`max_tracked_requests` budget was exhausted, even though every new
request ID then returns 503 `request_budget_exhausted`. The revised
`/readyz` now returns public 503 `admission_unavailable` once this
persistent capacity is reached. This check does not mutate counters and
does not count temporary rolling-window rate throttling as unavailability.
Already recorded request statuses remain readable; `/livez` remains
200. A Rust HTTP regression verifies all of these distinctions.

This still cannot promise acceptance under concurrent requests because
capacity can be exhausted immediately after the probe. A capacity change
requires an operator-approved restart/reconfiguration, not a fake
automatic counter reset.
