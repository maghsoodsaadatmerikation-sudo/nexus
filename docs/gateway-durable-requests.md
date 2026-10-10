# Durable HTTP request admission

The executable now opens `NEXUS_DATA_DIR/requests` before listening. The library's
`AppState::new` / `authenticated` remain explicitly ephemeral unless configured
with `with_request_store`. Use one gateway process per directory on a local
filesystem that supports file and directory `sync_all`; shared/network storage
and distributed admission are unsupported.

A hex-encoded request ID (1–100 UTF-8 bytes) names a marker, never a payload or
an authority grant. `create_new`, file sync and directory sync precede delegation.
Successful delegation with the same ID writes and syncs `pending\n` before 202.
GET returns the existing `request_id` and `pending` status after reopening.
An empty or partially written marker recovers as `indeterminate`: execution may
or may not have happened. Delegate errors also retain the reservation. Repeated
IDs return 409 without execution. Storage failures return 503. Invalid markers
block startup. Admission capacity includes recovered IDs; rate limits reset on
restart. Markers are not automatically deleted or replayed.

This is conservative duplicate prevention, not exactly-once execution: a crash
after reservation can prevent execution, while a crash after execution can lose
its acknowledgment. `pending` is the existing HTTP acceptance status, not proof
of completion. Ephemeral delegates retain their existing retry behavior.

Tests cover recovered acceptance and capacity, uncertain delegate errors, torn
markers, corruption, unavailable storage and synchronized 32-request contention.
The read-only verification harness also destroys and restarts the HTTP container
on the same mount, verifies GET and rejects repeated POST with 409.

Self-critique: synchronous filesystem writes block the request worker; filesystem
loss or removal of this directory removes replay protection. Workspace JSON
export/restore does **not** back up request markers and must not be presented as
full gateway recovery. Preserve the complete data volume for this guarantee.
Multi-process capacity/rate coordination, durable executor outcomes and retry
resolution remain outside this change. No automatic re-execution is safe here.

Evidence is not authority. Gateway markers never construct `AuthorizedRequest`;
only the core authorizes execution. `A_out ≤ A_in`, CT-001..020, Bootstrap/Verify
separation and both pinned Cargo.lock files remain required. This change does
not constitute a new Seal, attestation or deployment claim.
