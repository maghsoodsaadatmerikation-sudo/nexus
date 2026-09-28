# NEXUS v2.2.0 — Revocation Replay Integrity

**Status: SEALED / VERIFIED AT THE STATED REVOCATION-REPLAY BOUNDARY**

## Exact boundary

- Release tag: `v2.2.0`
- Exact candidate: `387efdf9d608d8e5ca5e706e9f6fa7480d49489c`
- Invariant: `A_child <= A_parent <= A_in`
- NEXUS v2.2 Revocation Replay Verification: run `36343709684` — SUCCESS
- Canonical NEXUS Verification: run `36343709655` — SUCCESS
- NEXUS v2.2 Release Gate: run `36343740275` — SUCCESS
- Release evidence SHA-256: `125cf27b5a17cffe1cccd0e956589d580e31ba51f90989f98e875bfaf8ef45fa`

## Verified claims

- Revocation state is reconstructed from ordered, provenance-bearing events.
- Unsupported schemas, broken sequences, empty grant identifiers, and empty provenance fail closed.
- Duplicate revocation is idempotent in effective state while remaining observable in append-only history.
- Revocation can only reduce future delegated authority.
- Exact-candidate evidence members pass SHA-256 self-audit after extraction from the bound evidence archive.

## Explicit non-claims

This seal does not claim durable or distributed revocation persistence, cryptographic event authenticity, consensus, external identity federation, provider correctness, universal security, production mutation, or authority beyond the parent/input boundary.

The v2.2 release does not retroactively seal the historical v2.0 engineering milestone and does not rewrite any earlier immutable release boundary.
