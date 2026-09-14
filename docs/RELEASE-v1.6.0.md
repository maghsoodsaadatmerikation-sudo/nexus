# NEXUS v1.6.0 — Exact Promotion Execution Record

Status: **CANDIDATE / AWAITING EXACT-COMMIT VERIFICATION**

NEXUS v1.6.0 advances the v1.5 promotion-safety boundary by recording an exact provider-side source pin and a successful post-change production deployment on the existing Railway service.

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

## Release gate

The historical `v1.6.0` release may be created only after the exact release-intent commit completes `NEXUS Verification` successfully. The release automation must bind the tag and release notes to that exact successful workflow-run SHA.

## Claim boundary

If the release gate passes, v1.6.0 may claim:

- exact provider-side production source pin to the sealed v1.4.0 commit;
- a new successful provider deployment after that pin;
- preserved `/data` persistence and authentication configuration;
- no paid expansion and no new authority surface introduced by the promotion.

It may not claim formal epistemic proof, universal security, universal availability, or stronger provider provenance than the recorded evidence supports.

Canonical provider evidence: `evidence/v1.6/railway-promotion-evidence.json`.
