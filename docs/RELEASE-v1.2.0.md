# NEXUS v1.2.0 — Sealed Release Record

Status: **SEALED / VERIFIED AT THE STATED OPERATIONAL BOUNDARY**

Release tag: `v1.2.0`

Sealed candidate commit:

```text
fbe17b80206df5e63f7351cc97f1794eb8c88e17
```

NEXUS Verification run:

```text
34848797043 — SUCCESS
```

Evidence artifact digests:

```text
verification-bundle: sha256:3bf37901f06074c6b42cbe322427c21e1f6be8da10cfd01a55e160d3993370ba
artifact-05-verification-bundle: sha256:1e6ee2695c8c40a015b15de00c8a8310a75ddc57922eab6d813179e6cc0547ac
render-stage-d-configuration: sha256:e3f280cc6d2e3d30826cc96f1f57f048064ae910b480f041e46321dab878c932
```

## Verified v1.2 gates

- G1 Release-boundary integrity: PASS
- G2 Continuous verification: PASS
- G3 Durable-state resilience: PASS
- G4 Operational economy: PASS
- G5 Release-candidate gate: PASS
- Exact-candidate GitHub verification: SUCCESS
- Human release decision: APPROVED
- Tag created: YES
- GitHub Release published: YES

## Operational boundary

The v1.2 release adds and verifies operational-resilience controls around the already sealed durable-host v1.1 boundary. Continuous verification runs on source changes and at 00:00, 08:00, and 16:00 UTC. Scheduled verification may verify and attest evidence but has no release authority.

The primary durable service and `/data` volume were preserved. No paid resource upgrade was requested or performed for v1.2. Auxiliary evidence services are non-production helpers configured with restart policy `NEVER` and sleeping enabled. The available Railway action rejects a literal zero-replica configuration, so this release does not claim provider-side zero replicas.

## Constitutional boundary

The invariant remains:

```text
A_out <= A_in
```

This release seals an operational verification boundary. It does not claim formal proof of epistemic correctness, universal availability, universal disaster recovery, or provider-wide billing guarantees. It does not authorize machine judgment or expand execution authority.

Historical tags `v1.0.0` and `v1.1.0` remain immutable earlier boundaries. Later development does not retroactively change their claims or evidence.
