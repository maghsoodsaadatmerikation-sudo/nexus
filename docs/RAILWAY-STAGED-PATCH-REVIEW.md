# Phase 34 — exact-diff Railway staged-change review

This gate is a **read-only review** of the specifically observed pending
Railway Stage D change, not a generic deploy controller. It is separate from
the Phase 33 *post-application* cutover preflight. Exact diff acceptance is
**not** deployment authorization and never modifies the Railway environment.

## Provider observation (2026-11-17)

The connected Railway metadata for project `2ac7887b-d67a-48be-8a7b-bd54092893ae`,
production environment `56c4bc45-0e62-4aa9-832f-884bb1aa620c`, reports a staged
patch `5439a0d6-3921-4746-8545-29313d3d7437` for service
`0032fc74-2c52-475d-b9df-9dca59237d93` (name `nexus-stage-d`).

The exact two provider-reported entries are:

| Field | Current | Staged | Meaning |
| --- | --- | --- | --- |
| `deploy.healthcheckPath` | `/` | `/readyz` | Makes the platform check actual readiness instead of a generic root response |
| `deploy.sleepApplication` | `true` | `true` | No effective value change; should not be counted as a fix for an asleep service |

The provider labels this patch `destructive=false`, with no shared-variable or
private-network change. **This alone does not authorize the update.** The
service is separately observed `SLEEPING`, is pinned to an older commit, and
holds its original `/data` volume. A mounted volume is not proof of an
offsite, decryptable backup or tested recovery.

## Command and input

Capture the raw result from the Railway **get_staged_changes** read-only action
for the **exact** project/environment. Use a private operator machine; never
put the capture or tokens into GitHub or a public artifact. Wrap the result:

```json
{
  "schema": "nexus.railway-staged-patch-capture.v1",
  "captured_at_utc": "<actual UTC timestamp of capture>",
  "staged_changes": {}
}
```

Replace `{}` with the *actual exact* `get_staged_changes` response, not a
reconstructed or mock status. Save as a single-link regular local file with
owner-only permissions (`chmod 600`). The tool will refuse files with
symlinks, multiple hard links, unsafe permissions, duplicate JSON keys, and
oversized contents. Capture must be younger than 15 minutes (with up to one
minute clock skew). The timestamp is supplied by the operator and is **not
cryptographically authenticated**.

```sh
python3 scripts/review-railway-staged-change.py \
  --input /private/railway-staged-patch.json
```

Exit 0: **MATCH** — exactly the known patch is still staged and is eligible
for separate human review. Exit 2: **BLOCKED** — stop, re-read Railway state
and inspect unexpected values. `MATCH` can include a warning if the patch
has not been edited for >72 hours; the alert is not evidence of recent human
approval. Both outcomes always emit `deployment_authorized=false`,
`production_mutation=false`, `live_change_applied=false`.

## Requirements before any separate deploy decision

1. Confirm a fresh complete source/deployment/current health report, actual
   readiness endpoint, and absence of other staged or applying work. Verify
   the exact SHA that the provider will deploy. The Phase 33 cutover gate
   deliberately blocks *all* staged changes until separately resolved.
2. Preserve independently held, recently verified off-host encrypted backup
   and execute a **non-destructive recovery rehearsal** before changing
   the volume-bound service. Historical release evidence and a mounted disk
   do not replace a recent backup and tested recovery.
3. Obtain explicit operator approval after reviewing the actual proposed
   changes. Do not call accept-deploy, restart, redeploy, or change a volume
   as a side effect of either reviewer or CI. Keep `A_out <= A_in`.

## Verification and limitations

```sh
python3 -m py_compile scripts/review-railway-staged-change.py scripts/test-review-railway-staged-change.py
python3 scripts/test-review-railway-staged-change.py
```

The CI job uses only disposable synthetic fixtures and read-only repository
permission. It never contacts Railway and cannot demonstrate external
readiness, independently signed deployment identity, durability, current
backup possession, or release approval. It checks only the guard logic.
