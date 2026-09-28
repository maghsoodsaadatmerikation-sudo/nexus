# NEXUS v1.6.0 — Exact Promotion Execution Record

Status: **SEALED / VERIFIED AT THE STATED EXACT-PROMOTION BOUNDARY**

Release tag: `v1.6.0`

Sealed candidate commit:

```text
60fc683808d4bed11b051546d7215aff50df0ade
```

NEXUS Verification run:

```text
34881242396 — SUCCESS
```

## Constitutional invariant

```text
A_out <= A_in
```

## Promotion target

```text
release: v1.4.0
commit: dcf49302e8a8c4c935de3aad0585b19132bad2cd
provider: Railway
project: NEXUS Stage D
service: nexus-stage-d
environment: production
durable mount: /data
```

## Provider-side promotion evidence

- Active source binding: `source.commitSha=dcf49302e8a8c4c935de3aad0585b19132bad2cd`
- Post-change deployment: `bc72bf4d-7e0b-4f19-9a74-25ca2f76d917`
- Deployment conclusion: `SUCCESS`
- Railway-built container image digest: `sha256:7c5741aafbd62520f5d5c734163820dfae59e9e05c3d0b131e96efc1359e6260`
- Durable volume remained mounted at `/data`
- Domain remained `nexus-stage-d-production.up.railway.app`
- Startup evidence retained `data_dir=/data` and `auth=configured`
- No secret values are included in the release evidence
- No paid resource upgrade was authorized or used

## Metadata distinction

The provider deployment object retains trigger/context metadata showing:

```text
meta.commitHash = 81f493b1fe3bc964bba51df905c2d448af13bdf4
meta.branch = main
```

NEXUS records this discrepancy rather than erasing it. That trigger/context field is not used here as proof of selected-source identity. The exact-source claim is limited to the active Railway `source.commitSha` configuration, followed by the successful deployment created after that configuration was committed.

Accordingly, v1.6.0 does **not** claim that Railway trigger metadata independently proves the selected source, nor does it claim independent binary reproducibility from the provider metadata alone.

## Release gate — PASS

The exact release-intent candidate `60fc683808d4bed11b051546d7215aff50df0ade` completed `NEXUS Verification` successfully in run `34881242396`. GitHub release `v1.6.0` was published with `target_commitish` equal to that exact verified candidate.

The canonical promotion evidence digest recorded in the release is:

```text
sha256:5a8a3542356257881540480a521dbb21aad0e78bee905c56bbacad8e8bfd4aef
```

## Claim boundary

v1.6.0 may claim:

- exact provider-side production source pin to the sealed v1.4.0 commit;
- a new successful provider deployment after that pin;
- preserved `/data` persistence and authentication configuration;
- no paid expansion and no new authority surface introduced by the promotion.

It may not claim formal epistemic proof, universal security, universal availability, independent binary reproducibility from Railway trigger metadata, or stronger provider provenance than the recorded evidence supports.

The `v1.6.0` tag is the immutable historical boundary. This file on `main` is a post-seal record and does not alter that historical tag.

Canonical provider evidence: `evidence/v1.6/railway-promotion-evidence.json`.
