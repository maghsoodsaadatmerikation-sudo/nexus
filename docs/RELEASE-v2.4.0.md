# NEXUS v2.4.0 — Gateway Authority-Confusion Defense

**Status: SEALED / VERIFIED AT THE STATED GATEWAY BOUNDARY**

## Exact boundary

- Release tag: `v2.4.0`
- Exact candidate: `0ba1a8efe21f3da68cc44cf5f6988cb59055fd3f`
- Invariant: `A_out <= A_in`
- NEXUS v2.4 Gateway Authority-Confusion Verification: run `36382808938` — SUCCESS
- Canonical NEXUS Verification: run `36382808948` — SUCCESS
- NEXUS v2.4 Release Gate: run `36382857043` — SUCCESS
- Exact-candidate evidence attestation: VERIFIED
- Evidence artifact ID: `10953228757`
- GitHub artifact ZIP digest: `sha256:a5254df6e07da255e62e774db82fd4182f9561d110edc011b744373695a1a222`
- Attested evidence archive SHA-256: `a9876f392c2f4e948ca35de618a6691acfdddafc9cc00d04fb9f5da585eab4e2`
- Extracted evidence-member SHA-256 self-audit: PASS

## Verified claims

- `POST /v1/requests` accepts only the exact tagged request schema.
- Unknown and authority-like fields are rejected with `422` before delegation.
- Rejected ambiguous inputs never reach `ConstitutionalDelegate`.
- No capability-mint, revocation, authorization, or policy-mutation route is exposed.
- Valid exact-schema requests retain asynchronous `202 Accepted`.
- `GET /v1/requests/{id}` retains status/`404` semantics.
- Authority expansion: NONE.

## Release-note rendering defect

The GitHub Release is correctly targeted to the exact candidate and the release gate asserted that binding. Its generated human-readable notes omitted interpolated SHA/run/digest values because Markdown backticks in the shell heredoc triggered command substitution. This post-seal record supplies those values from the immutable successful runs and downloaded attested evidence. It does not rewrite the historical tag or expand the sealed claims.

## Explicit non-claims

This seal does not claim that HTTP authenticates authority, that clients are trustworthy, cryptographic transport authenticity, durable or distributed persistence, consensus, federation, provider correctness, universal security, production mutation, or external-system linearizability.

The v2.4 release does not rewrite any earlier immutable release boundary.
