# Rust gateway Authorization field identity — 14 November 2026

## Observed structural weakness
The authenticated constitutional gateway previously evaluated one value via
`HeaderMap::get(AUTHORIZATION)`. When the incoming HTTP field occurs more
than once, an intermediary and the Rust gateway can disagree about which
bearer credential was supplied. This behavior differed from stricter
duplicate-field checks introduced in the optional cloud-adapter branch
(#196) and could affect direct Rust gateway traffic.

## Correction in this candidate
- The Rust gateway now requires **exactly one** `Authorization` field
  whenever a bearer token is configured; absent, repeated, or malformed
  credentials fail with the existing HTTP 401, without querying or
  mutating the constitutional delegate.
- Uses a bytewise mismatch accumulator that visits every byte of the
  configured token rather than a short-circuiting prefix equality.
  This is a best-effort timing improvement; compiler, hardware, network,
  header-length and length-dependent effects prevent claiming a formal
  constant-time guarantee.
- Preserves explicit local unauthenticated mode when no token is configured.
  That mode must never be exposed on an untrusted network.
- Keeps existing response codes, request shapes, safety budgets,
  workspace boundaries and cache-control behavior.

## Adversarial tests
Tests exercise repeated correct tokens, conflicting repeated tokens in both
orders, short/long/whitespace/case-changed Bearer values, read and write
routes for both requests and workspaces, and valid single-token submission.
Tests assert unauthorized requests do not reach the request delegate.

## Known unresolved structural issues
This change does not integrate #129–#134, alter production secrets or
provider settings, prove off-provider backup/restore, make GitHub status
checks strict/up-to-date, or authorize any main merge. The same
`artifact-05/src/lib.rs` and `artifact-05/tests/http_contract.rs`
are changed in draft PR #130, so a future integration must reconcile
them and rerun exact-head Rust, HTTP and durable-state tests. Token
authentication is not per-user authorization or a substitute for TLS.

**Release hold:** draft source-only repair; no main merge, deployment,
production data mutation, release tag or Stage D attestation.
