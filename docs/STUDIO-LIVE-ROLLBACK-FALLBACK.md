# Current-live NEXUS Studio public-source recovery candidate

## Read-only Render metadata — 22 November 2026

The owner-confirmed Render workspace \`My Workspace\` (\`tea-dabhioe10ojc73acbs8g\`) reported:

| Verified provider metadata | Observation |
|---|---|
| Static service | \`nexus-studio-merikation\`, \`srv-dbrjurc9v7es73cqe0v0\` |
| Public origin | \`https://nexus-studio-merikation.onrender.com/\` |
| **Live deploy** | \`dep-dc0j4sh7lnhs738r3r00\`, status \`live\` |
| **Live source Git commit** | \`826c91e2053f716b9aa7e40713f3c568e5272eba\` |
| Render deployed time | 21 November 2026, finished 05:56:27 UTC |
| Branch and repo | \`main\`, \`maghsoodsaadatmerikation-sudo/nexus\` |
| Build / publish | \`python3 scripts/build-studio-static.py --check\`, \`public/studio\` |
| Studio AutoDeploy | **OFF**, as reported in the connected Render service settings |
| Immediately preceding deploy | \`dep-dc0c4mks728c738g321g\`, source \`8fd2a3825a2c6ea41adec75a222ca738d59bf6ca\`, status \`deactivated\` |

The older snapshot \`8b5da6a192e6be68283282afcb2ac9b5d0fdcd91\`, deploy \`dep-dbvvvil9fdbs73c6qb80\`, was **already deactivated** when checked. It was used by the previous 13-file/nine-HTTPS-path fallback workflow and **must not** be described as a snapshot of the currently live Studio site.

The independently observed Git \`main\` branch is ahead of the live Studio source; Studio AutoDeploy is disabled. The separate Render web service called \`nexus\` has **AutoDeploy enabled**; do not confuse it with this separate static Studio service. Committing to \`main\` can update that other public service without a manual deploy action.

**Important separation of evidence:** the provider API attests deploy metadata at the time of the read-only query. The following GitHub workflow independently tests public HTTPS bytes. It does **not** re-query Render deploy metadata; a matching website does not prove the provider still reports the same deploy ID later. Both observations can become stale.

## Complete read-only current-live source snapshot

The [Current-Live Complete Public Source Fallback workflow](https://github.com/maghsoodsaadatmerikation-sudo/nexus/actions/workflows/studio-live-source-fallback.yml) checks out two revisions without persistent credentials:

1. The exact candidate tool source (\`github.sha\`) containing the tested verification code.
2. The independently observed live Render Git revision \`826c91e2053f716b9aa7e40713f3c568e5272eba\` with exactly **17** reviewed \`public/studio/\` files.

It rejects any unlisted private file, symlink, missing module or over-limit asset and verifies that the old source's \`service-worker.js\` pins its own HTML hash. It then performs **17 real read-only GETs** at the fixed public HTTPS origin (all original 13 files plus four bundled PDF module/license files). Strict MIME checks, redirects disabled, response byte bounds and PNG RGBA pixel equality prevent wrong-endpoint responses or reencoded icon containers from misleading the source match.

All HTML, JavaScript, model metadata, PDF workers/modules and license files must match source **byte-for-byte**. Only the two PNG icons may be \`PIXEL_MATCH\`, meaning their decoded RGBA pixels match despite a different PNG container. If **any** source file is unavailable, altered or incorrectly typed, the source archive is not published. A successful report proves source **parity at observation time**, not user acceptance or Render deploy identity.

On successful completion GitHub Actions retains for 30 days:
- \`nexus-studio-previous-live-source.zip\` — deterministic, SHA-bound ZIP with exactly 17 reviewed public source files; the legacy filename is retained for continuity
- \`nexus-studio-previous-live-source.zip.sha256\` — archive SHA-256 sidecar
- \`nexus-studio-previous-live-witness.json\` — source-commit/deploy-at-snapshot identifiers and 17 path status codes

The archive does **not** include user conversations, encrypted vaults, saved drafts, private environment variables, provider API keys, real model weights, Render service state or Railway Stage D volumes. It does not perform a deploy, a rollback or a recovery of browser IndexedDB storage.

## Required checks before a subsequent authorized promotion

1. Re-read the static Render service and current deploy ID before promotion. **If either differs from this dated snapshot, stop and create a new exact-revision recovery witness.** The workflow's static pin intentionally does not silently follow later deploys.
2. Keep the successful GitHub ZIP, checksum and witness accessible outside any transient runner before publishing a newer site. Re-verify hashes and file count.
3. In the [Render Studio dashboard](https://dashboard.render.com/static/srv-dbrjurc9v7es73cqe0v0), check whether the prior successful deployment is *actually eligible* for Render's rollback action. The Render connector here can read deploy records but **does not expose proof of retained build artifacts or a rollback operation**. A deploy record with status \`deactivated\` does not prove Rollback is presently available.
4. Obtain separate service-specific owner permission before doing anything mutating. The connected Render \`trigger_deploy\` action does not pin a source SHA; a newer \`main\` commit could be deployed unintentionally. Use an independently reviewed exact-source deployment procedure, not an unbounded latest-branch command.
5. After deployment, require fresh public-source, real Chromium offline/encrypted-vault acceptance, Android owner-device QA and appropriate provider/cost safety checks. Independently record the new deploy ID and service settings.
6. If verification fails, a human operator can initiate a **separately authorized** rollback only if the Render Dashboard currently offers a retained build-artifact rollback. Otherwise a separate source-based restoration process may be evaluated; this ZIP is **not** an immediately deployable or guaranteed zero-downtime rollback.

## Explicit safety limits

- Passing this fixed-source workflow is **a recovery-source snapshot**, not production release permission.
- No Render or Railway tokens are made available to CI; no paid provider request or new paid service is created.
- A source ZIP cannot recover private browser data, prove actual model quality or confirm an old Render build artifact is retained.
- Existing releases may change while GitHub Actions runs. Repeat the read-only provider metadata and HTTPS observations immediately before a separately authorized deployment.
- Do not disable or modify AutoDeploy for the separate \`nexus\` web service without an explicit owner decision.
