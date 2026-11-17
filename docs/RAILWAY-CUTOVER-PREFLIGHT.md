# Railway production cutover — read-only preflight (2026-11-17)

**Scope:** operator-supplied, sanitized Railway metadata + actual public GET
observation. This gate evaluates a **single exact candidate**, refuses a stale
or inconsistent snapshot, and NEVER deploys, triggers a build, changes a volume,
restarts a service, changes variables, imports data or approves a release.

It is deliberately independent of Phase 30–32 draft snapshot/restore branches.
This PR is based on main and grants no new cloud, model, GitHub or Docker power.

## Observed provider state on 2026-11-17

Read via the connected Railway project inventory and deployment API:

- Actual project: `NEXUS Stage D` / `2ac7887b-d67a-48be-8a7b-bd54092893ae`.
  A similarly named second project currently has **no services**; do not use
  the project name alone to select an operational target.
- Production environment: `56c4bc45-0e62-4aa9-832f-884bb1aa620c`.
- Main service: `0032fc74-2c52-475d-b9df-9dca59237d93`;
  public domain `nexus-stage-d-production.up.railway.app` on port 3000.
- Mounted volume: `cc47a350-6c7e-4487-89d9-c4b390f94884`,
  mounted at `/data`; the provider reports a volume but this is **not**
  evidence of an independent copy or verified restoration.
- Deployment `32cdcb2b-c03c-4a6f-b028-27a9977717ce` reported
  `SLEEPING`, built from `9abbc067aad3ebbb0956432cf6682d2ea70e2824`.
  The main branch had subsequently advanced beyond that revision.
- Pending staged patch `5439a0d6-3921-4746-8545-29313d3d7437`
  contains a healthcheck change **from `/` to `/readyz`** and a
  recorded `sleepApplication true -> true` entry. This is not
  automatically committed: an unreviewed patch must block cutover.
- `NEXUS_API_TOKEN`, `NEXUS_DATA_DIR`, `NEXUS_BIND_ADDR` and `PORT`
  are configured by *variable name*. Their values and correct behavior are
  NOT established by the inventory.
- No public GET observation or independent current offsite backup was
  authenticated in this examination. Prior historical release seals remain
  historical; they do not prove the current commit is deployed or recoverable.

This is a dated snapshot, not a continuous health guarantee.

## Inputs

Keep the original source files private and outside the public Git repository.
Create a **single JSON document** containing exact results of these five
read-only operations made in the same short observation window:

- `Railway.describe_environment` -> `inventory`
- `Railway.describe_service` -> `service`
- `Railway.environment_status(includeSuccessful=true)` -> `health`
- `Railway.list_deployments(serviceId=<exact id>)` -> `deployments`
- `scripts/observe-pilot-runtime.py` -> `public_observation`

The document has a top-level schema and UTC capture timestamp:

```json
{
  "schema": "nexus.railway-cutover-input.v1",
  "captured_at_utc": "2026-11-17T10:00:00Z",
  "inventory": {},
  "service": {},
  "health": {},
  "deployments": {},
  "public_observation": {}
}
```

Replace these five empty objects with the **full actual tool JSON objects**;
never fabricate provider status or a public observation. Only place this
snapshot on a trusted private operator machine; deployment records may
contain identity metadata. The script reads at most 256 KiB, refuses symlinks,
duplicate JSON keys and nonfinite JSON numbers, and never outputs raw input.

Compute the candidate's canonical source digest from the exact reviewed
checkout using `bash scripts/source-tree-digest.sh`. Separately execute the
existing public observer with the same digest:

```sh
python3 scripts/observe-pilot-runtime.py \
  --origin https://nexus-stage-d-production.up.railway.app \
  --expected-digest "$(bash scripts/source-tree-digest.sh)"
```

Then run the provider+public gate against the combined private document:

```sh
python3 scripts/check-railway-cutover.py \
  --input /private/railway-current-snapshot.json \
  --expected-project-id 2ac7887b-d67a-48be-8a7b-bd54092893ae \
  --expected-service-id 0032fc74-2c52-475d-b9df-9dca59237d93 \
  --expected-volume-id cc47a350-6c7e-4487-89d9-c4b390f94884 \
  --expected-origin https://nexus-stage-d-production.up.railway.app \
  --expected-commit "<exact-reviewed-40-hex-candidate>" \
  --expected-digest "<exact-reviewed-64-hex-source-tree-digest>"
```

Add `--always-on` when requiring non-sleeping production configuration.
On-demand mode does NOT equate to guaranteed availability; live observation
still requires an actual online deployment. Exit 0 means only these
**technical preflight checks were satisfied**; exit 2 means blocked.

## Checks and critical limits

The gate requires the correct project and production environment, no pending
patch, exact service and main source SHA, matching actual deployment SHA,
real `SUCCESS` deployment / online health, configured `/readyz`, correct
persistent volume mount, named variables and HTTPS domain:3000, plus fresh
public GET results with verified build-metadata digest and exact protected
route 401 responses. It refuses stale input/observation (>30 min), missing
or malformed sections, unsupported identity and conflicting provider signals.

A passing report **always** says:
`production_release_authorized=false`;
`independent_offsite_backup=NOT_ASSESSED`;
`restore_rehearsal=NOT_ASSESSED`.
A self-reported digest is not signed binary attestation. The capture timestamp
is supplied by the operator and is not independently authenticated.

Before *any* separate deployment decision, use a independently held recent
encrypted/signed backup with a genuine off-host readback and non-destructive
restoration rehearsal, inspect the complete exact-head CI and security review,
and obtain explicit operator approval. Production modifications are
**not part of this PR**. Constitutional invariant: `A_out <= A_in`.

## Synthetic verification

```sh
python3 -m py_compile scripts/check-railway-cutover.py scripts/test-railway-cutover.py
python3 scripts/test-railway-cutover.py
```

The restricted PR workflow uses synthetic fixtures without Railway credentials
or network calls and has only `contents: read` permission. A CI PASS tests
the gate, **not** a real provider or production cutover.
