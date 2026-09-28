# NEXUS v1.5.0 — Sealed Promotion-Safety Record

Status: **SEALED / VERIFIED AT THE STATED PROMOTION-SAFETY BOUNDARY**

Release tag: `v1.5.0`

Sealed candidate commit:

```text
84d1c283494e1203e63d6a892351938dfc24a5ed
```

NEXUS Verification run:

```text
34879097015 — SUCCESS
```

Promotion target:

```text
v1.4.0 @ dcf49302e8a8c4c935de3aad0585b19132bad2cd
```

Pre-cutover rollback anchor:

```text
commit: 480f8771c47e41d4d19b22ed4360bd32c4d2f70a
deployment: 1f63e3b9-768f-441e-a524-b061394b922e
provider: Railway
service: nexus-stage-d
durable mount: /data
```

## Verified promotion-safety gates

- G1 Historical release integrity: PASS
- G2 Promotion target identity: PASS
- G3 Pre-cutover durable-state safety: PASS
- G4 Exact-SHA execution requirement: PASS
- G5 Post-cutover evidence requirement: PASS
- G6 Rollback readiness: PASS
- G7 Operational economy: PASS
- G8 Exact-candidate release gate: PASS

## Production truth

Production promotion was **not performed** as part of v1.5.0. The connected provider tooling did not expose a verified exact-commit source pin for the existing primary service. NEXUS therefore refused to approximate an exact promotion through a moving branch.

This is a successful fail-closed result: release readiness and promotion execution remain separate epistemic and execution objects.

A future production cutover requires an immutable target binding plus new provider-side post-cutover evidence proving `SUCCESS`, the exact promoted identity, durable `/data`, and no authority expansion.

## Constitutional boundary

```text
A_out <= A_in
```

No paid resource upgrade, new service, or new volume was authorized or required. This seal is an operational promotion-safety boundary. It is not a claim of formal epistemic proof, universal availability, universal security, or current production deployment of v1.5.0 or v1.4.0.
