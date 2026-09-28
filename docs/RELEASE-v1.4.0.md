# NEXUS v1.4.0 — Sealed Release Record

Status: **SEALED / VERIFIED AT THE STATED RELEASE-TRUTH BOUNDARY**

Release tag: `v1.4.0`

Sealed candidate commit:

```text
dcf49302e8a8c4c935de3aad0585b19132bad2cd
```

NEXUS Verification run:

```text
34877496665 — SUCCESS
```

Release workflow run:

```text
34877753394 — SUCCESS
```

## Deployment-truth evidence

At candidate time, provider-side observation recorded:

- Provider: Railway
- Environment: production
- Service: `nexus-stage-d`
- Deployment ID: `1f63e3b9-768f-441e-a524-b061394b922e`
- Deployment status: `SUCCESS`
- Observed live commit: `480f8771c47e41d4d19b22ed4360bd32c4d2f70a`
- Durable data mount: `/data`
- Latest sealed predecessor: `v1.3.0` @ `458260fcadc95b53d5e33fa2fabf806519a8cccd`
- Reconciliation at candidate time: `LIVE_BEHIND_RELEASE`
- Authentication material recorded: NO
- Authority expansion: NONE

## v1.4 gates

- G1 Historical seal integrity: PASS
- G2 Live deployment attestation: PASS
- G3 Release/deployment reconciliation: PASS
- G4 Claim discipline: PASS
- G5 Durable-boundary continuity: PASS
- G6 Operational economy: PASS
- G7 Exact-candidate release gate: PASS

## Claim boundary

`released`, `verified`, and `observed-live` are separate claims. v1.4.0 is released and verified at the stated boundary. The observed Railway production service was not promoted to v1.4.0 as part of this release and therefore must not be described as running v1.4.0 without new provider-side evidence.

## Constitutional boundary

`A_out <= A_in`

This release records and reconciles deployment identity. It does not deploy, promote, authorize, repair, restore, interpret evidence meaning, or expand machine authority.

No paid resource upgrade was authorized or required. This is an operational release-truth seal, not a formal proof of epistemic correctness, universal security, universal availability, or production deployment of v1.4.0.
