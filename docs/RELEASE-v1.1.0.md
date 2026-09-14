# NEXUS v1.1.0 — Sealed Release Record

Status: **SEALED / VERIFIED AT THE STATED OPERATIONAL BOUNDARY**

Release tag: `v1.1.0`

Sealed deployed commit:

```text
480f8771c47e41d4d19b22ed4360bd32c4d2f70a
```

NEXUS Verification run:

```text
34824938788 — SUCCESS
```

Workspace snapshot SHA-256:

```text
71271177cadc1dd67afdf0ddbc913c89c54b326df66bdb2f1dd803da94107d7b
```

Stage D evidence-harness SHA-256:

```text
bd4aea44cd972a7f02523115dcecd1abd956f70beb7a71d1880d3da896940325
```

Stage E readiness-gate SHA-256:

```text
f3d1f97e5ab637b84e29c532b98a06de43e9e2fd94a0d3c8a8fedf1622b3321d
```

## Verified durable-host lifecycle

- HTTPS endpoint and public liveness: PASS
- Missing bearer rejected: PASS
- Wrong bearer rejected: PASS
- Authenticated witness capture: PASS
- Exact deployed commit binding: PASS
- Real service replacement event: RECORDED
- Witness survival after replacement without restore: PASS
- Destructive backing-state removal: RECORDED
- Authenticated `404 workspace_not_found` absence observation: PASS
- Snapshot restore: PASS
- Restored state JSON-equivalent to captured state: PASS
- Token recorded in evidence: NO
- Authority expansion: NONE

## Release gate

The lifecycle-bound evidence pack passed `scripts/v1.1-release-readiness.sh`. The referenced exact deployed commit also had a successful `NEXUS Verification` run that was independently checked before release publication.

Human release authorization was then given explicitly. The `v1.1.0` tag and GitHub Release were created against the exact tested commit, not against a later documentation head.

## Constitutional boundary

The invariant remains:

```text
A_out <= A_in
```

This release seals an operational verification boundary. It does not claim formal proof of epistemic correctness, general availability, load tolerance, or universal disaster-recovery guarantees. It does not authorize machine judgment or expand machine authority beyond explicitly authorized inputs.

Historical release boundaries remain immutable: later commits may document or extend NEXUS but do not retroactively change the claims or evidence attached to `v1.0.0` or `v1.1.0`.
