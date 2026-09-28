# NEXUS v2.5.0 — Unified Transport Authentication

**Status: SEALED / VERIFIED AT THE STATED TRANSPORT BOUNDARY**

## Exact boundary

- Release tag: v2.5.0
- Exact candidate: 200ff827efed0a165548e9dbc2b6801d23d6ddfb
- Invariant: A_out <= A_in
- NEXUS v2.5 verification run 36385219907: SUCCESS
- Canonical NEXUS Verification run 36385219924: SUCCESS
- NEXUS v2.5 Release Gate run 36385267448: SUCCESS
- Exact-candidate evidence attestation: VERIFIED
- Evidence artifact ID: 10954301032
- GitHub artifact ZIP digest: sha256:c4508a5573fc4912349a567cc04fd1fa1b3f6062569a87d4acf2bd9c54f73bb5
- Release evidence SHA-256: c64546d8b96e99338ba9cc41a93e0f825b151e8627b436d321ade31b5a432c46

## Verified claims

- Configured bearer authentication covers constitutional request submission and status lookup.
- Missing and incorrect credentials fail before body parsing, delegate invocation, or status lookup.
- Unauthenticated status requests cannot distinguish known from unknown request identifiers.
- A matching bearer preserves asynchronous 202 and status/404 behavior.
- Transport authentication creates no constitutional authority.
- Production mutation: NONE.
- Authority expansion: NONE.

## Explicit non-claims

This seal does not claim credential rotation, cryptographic channel authenticity beyond the deployment TLS boundary, external identity federation, rate limiting, distributed session state, durable persistence, consensus, universal security, or external-system linearizability.

The v2.5 release does not rewrite any earlier immutable release boundary.
