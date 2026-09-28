# NEXUS v1.3.0 — Sealed Release Record

Status: **SEALED / VERIFIED AT THE STATED OPERATIONAL BOUNDARY**

Release tag: `v1.3.0`

Sealed candidate commit:

```text
458260fcadc95b53d5e33fa2fabf806519a8cccd
```

NEXUS Verification run:

```text
34873937406 — SUCCESS
```

Release workflow run:

```text
34874211266 — SUCCESS
```

Evidence artifact digests:

```text
verification-bundle: sha256:d324c4c7ca0754e45c639b41cd3870e07c7b41712d1f7a532ffeeeaf47fedfab
artifact-05-verification-bundle: sha256:ca4fd0f730c1fe248ad41a38f5d2a6523ead6ef9450611e2f10caac31b7e3e51
render-stage-d-configuration: sha256:e97553dbb15da13d90ddb0723ea6d2418e9edfe7cbb0f3d3fd3701e5ee1b509c
```

## Verified v1.3 gates

- G1 Historical seal integrity: PASS
- G2 Gateway authority non-expansion: PASS
- G3 Secret and evidence hygiene: PASS
- G4 Provenance and dependency integrity: PASS
- G5 Failure transparency: PASS
- G6 Operational economy: PASS
- G7 Exact-candidate release gate: PASS
- Exact-candidate GitHub verification: SUCCESS
- Independent run check before publication: SUCCESS
- Human release decision: APPROVED
- Tag created: YES
- GitHub Release published: YES

## Operational boundary

The gateway remains constrained to its existing constitutional role. Production hardening adds fail-closed checks around historical seal integrity, gateway contract tests, secret-free evidence, immutable dependency references, failure transparency, and operational economy.

Scheduled verification remains observation/verification/attestation only. It has no release authority and no production repair authority. The durable `/data` persistence boundary remains preserved. No paid resource upgrade was authorized or required for this release.

## Constitutional boundary

The invariant remains:

```text
A_out <= A_in
```

This release seals an operational verification boundary. It does not claim formal proof of epistemic correctness, universal security, universal availability, or provider-wide billing guarantees. It does not authorize machine judgment or expand execution authority.

Historical release tags remain immutable earlier boundaries. Later work may add evidence or narrower operational controls, but does not retroactively alter the claims attached to `v1.0.0`, `v1.1.0`, `v1.2.0`, or `v1.3.0`.