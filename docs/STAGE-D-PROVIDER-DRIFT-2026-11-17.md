# Stage D — provider metadata drift triage (17 November 2026)

**Status: HOLD.** Read-only Railway metadata was inspected for the existing
`nexus-stage-d` service in the production environment on 2026-11-17. The
observations were obtained through the connected Railway service metadata
interfaces; they are **provider-reported configuration**, not a public runtime
attestation, filesystem inspection, cold backup, or restoration test.

## Three distinct source identities

| Identity | SHA | What it means |
| --- | --- | --- |
| GitHub `main` at observation | `4d97bafd840165469270e724195fd16ce8e33a13` | Current reviewed repository commit at the moment of inspection |
| Railway live source reported in config | `9abbc067aad3ebbb0956432cf6682d2ea70e2824` | Source associated with the latest service deployment, created 2026-11-13 |
| Historical v1.7 reconciliation workflow target | `3c0977f4c7fc9fb5e9a78bdb1eeb581cb3cb4959` | Fixed historical source target in the old job, **not** the live source |

GitHub independently identifies the second SHA as the historical
November 13 integration commit, and the third as a September 14 historical
v1.7 documentation commit. **Neither is today's GitHub main.** A current CI
verification PASS on GitHub does not imply the Railway service is running that
source. Likewise, the old v1.7 production reconcile may fail its source check
even with a healthy latest deployment because its target is historical.

## Current deployment/config metadata

- The most recent Railway deployment is marked `SUCCESS`, but **the
  running HTTP endpoint and exact source tree have not been independently
  interrogated in this review**. A deployment status alone is not readiness.
- The service's *live* health check remains `/`. A `/readyz` health check
  is **staged**, not applied. The staged patch contains two reported changes;
  one repeats `sleepApplication=true` and must not be assumed meaningful.
- Sleep-on-idle remains enabled in live config. A sleeping service can make
  observation timing or availability claims misleading.
- The original volume is reported mounted at `/data`. Mount metadata does
  **not** prove completeness, encryption, consistent backup, isolated restore,
  the absence of old-reader downgrade risks, or protection of user records.
- Another connected Railway project also has the name `nexus-stage-d` but
  no services. Project/name similarity is not a valid deployment locator.

No Railway patch was accepted, no wake/restart requested, no secrets or
volume contents read, and no billed resource created.

## Safe machine-checkable snapshot

The sanitized source is
[`evidence/stage-d-provider-metadata-2026-11-17.json`](../evidence/stage-d-provider-metadata-2026-11-17.json)
and a strict offline-only classifier lives at
[`scripts/stage_d_provider_preflight.py`](../scripts/stage_d_provider_preflight.py).

To check it from a checkout:

```sh
python3 scripts/stage_d_provider_preflight.py evidence/stage-d-provider-metadata-2026-11-17.json
python3 scripts/test_stage_d_provider_preflight.py
```

This emits `HOLD_INDEPENDENT_RUNTIME_AND_RECOVERY_EVIDENCE` and boolean drift
observations, with `release_authorized=false`. It does not fetch GitHub,
wake Railway, read the original volume, issue a paid action, push changes or
assert that the snapshot is still current. Malformed input, duplicate fields,
unexpected/private data or attempts to mark runtime/restore independently
verified are rejected. CI tests this **diagnosis**, not production readiness.

## Required next operational gates

1. Obtain an owner-approved **non-destructive runtime identity observation**
   of the actual service, using bounded credentials and explicit cost
   awareness for a potentially sleeping service. Compare the *live exact*
   source-tree digest with a reviewed release candidate. Treat 200 from
   `/` as liveness only; `/readyz` and Rust gateway state need a separate,
   version-appropriate acceptance protocol.
2. Review (do not automatically apply) the outstanding staged healthcheck
   patch and its impact on a sleeping service. Preserve the original mount and
   avoid hidden restart or deployment.
3. Acquire an authorized consistent, encrypted off-provider **private** copy
   of the complete original state, then independently restore the copy to an
   isolated disposable environment with verified hashes and without writing
   to the production volume. Never publish backups, tokens or file lists
   containing private user data to GitHub, chat or CI.
4. Require real device acceptance separately for the Pilot 12 PWA
   ([issue #271](https://github.com/maghsoodsaadatmerikation-sudo/nexus/issues/271))
   and do not conflate that legacy static pilot with authenticated Rust Stage D.
5. Only after exact runtime, recovery, security and owner-authorized release
   conditions are separately met can a specific release be considered.

**Self-critique:** A version mismatch is an operational blocker, not proof
of a security exploit or data loss. A provider `SUCCESS` is not evidence of
a reachable or authenticated HTTP endpoint. The provider snapshot is dated
and may already be stale. This read-only diagnosis never replaces
independent signed release evidence. `A_out <= A_in`.
