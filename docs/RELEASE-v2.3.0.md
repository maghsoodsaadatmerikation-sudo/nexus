# NEXUS v2.3.0 — Revocation Freshness / Stale-Authority Defense

**Status: SEALED / VERIFIED AT THE STATED REVOCATION-FRESHNESS BOUNDARY**

## Exact boundary

- Release tag: `v2.3.0`
- Exact candidate: `9da19fbc49ffed5752888d7ab41068266a59f918`
- Invariant: `A_child <= A_parent <= A_in`
- Freshness rule: `revocation observed => stale authorization cannot restore authority`
- NEXUS v2.3 Revocation Freshness Verification: run `36345103234` — SUCCESS
- Canonical NEXUS Verification: run `36345103184` — SUCCESS
- NEXUS v2.3 Release Gate: run `36345130192` — SUCCESS
- Exact-candidate evidence attestation: VERIFIED
- Release evidence SHA-256: `6fcf7d3d2b2214c6fa301aa517346faa1efd49bab6407ad942bc2df8cfed0675`

## Verified claims

- Delegated authorization is opaque and bound to the validated revocation epoch and complete ordered snapshot.
- Execution rechecks the current revocation state before consuming delegated authority.
- Newer and older epochs reject cached authorization fail-closed.
- Equal-epoch divergent histories reject authorization fail-closed.
- Reauthorization is required after every revocation-state transition.
- The evidence archive is attested and all extracted members pass SHA-256 self-audit.

## Explicit non-claims

This seal does not claim durable or distributed revocation persistence, cryptographic event authenticity, consensus, external identity federation, provider correctness, universal security, production mutation, or external-system linearizability.

The v2.3 release does not retroactively seal the historical v2.0 engineering milestone and does not rewrite any earlier immutable release boundary.
