# Stage D: exact deployed-commit coherence and non-disruptive recovery preflight

## Actual Railway observation (read-only, 15 November 2026)

In the connected Railway project \`NEXUS Stage D\`, provider-declared deployed revisions on the latest active deployments differ:

| Role | Service | Reported commit | Railway deployment | Region |
| --- | --- | --- | --- | --- |
| Original | \`nexus-stage-d\` | \`9abbc067aad3ebbb0956432cf6682d2ea70e2824\` | \`SLEEPING\` | \`sfo\` |
| Restore | \`nexus-stage-d-restore\` | \`588dc7672146031425b16b34956876d644244ace\` | \`SLEEPING\` | \`us-west2\` |

The independent Stage D runner was offline at inspection, and an unapplied Railway environment patch remains. Two separately mounted \`/data\` volumes exist in different provider regions, **but different regions and different Git commit IDs do not prove two independently controlled machines or a successful recoverable snapshot**. These deployment revisions are provider *metadata*, not cryptographic runtime attestation; a sleeping service may not presently execute any code.

The required next real-world action is **not** to start or deploy either service casually. First reconcile the approved release commit and the exact historical release/restore compatibility protocol on an isolated, operator-reviewed plan. An unmanaged redeploy could use an inappropriate revision or affect a mounted persistent volume. This PR never touches provider infrastructure.

## New offline operator verifier

\`scripts/workspace-stage-d-deploy-coherence.py\` accepts **four independently exact-SHA-256-pinned JSON snapshots** obtained by an authorized operator from the Railway connector's read-only actions:

1. \`describe_environment\` (project and services, mounted volumes, recorded latest deployments, regions and staged patches)
2. \`environment_status(includeSuccessful=true)\` (actual reported online/sleeping state, active deployment IDs and running replica counts)
3. \`list_deployments(projectId=...,serviceId=SOURCE,limit=...)\` for the original Stage D service
4. \`list_deployments(projectId=...,serviceId=RECOVERY,limit=...)\` for the restoration service

Keep each snapshot's exact bytes separately and capture its SHA-256 in a **different, independent trust/custody domain**. Do not treat a digest calculated from the downloaded untrusted file at verification time as an independent witness. Public connector metadata is not provider-signed cryptographic testimony.

Provide an operator-approved *full* 40-character expected Git SHA, not merely a branch name or a 7-character abbreviation. The verifier validates provider-reported repository, distinct expected services and volumes, environment, active deployment IDs, actual listed deployment histories, matching source branch \`main\`, recorded regions, full commit hashes, the runtime state and the original preflight's pending-patch checks.

\`\`\`sh
python3 scripts/workspace-stage-d-deploy-coherence.py inspect \
  --inventory /private-review/railway-inventory.json \
  --inventory-sha256 INDEPENDENT_SHA256_INVENTORY \
  --health /private-review/railway-health.json \
  --health-sha256 INDEPENDENT_SHA256_HEALTH \
  --source-deployments /private-review/source-deployments.json \
  --source-deployments-sha256 INDEPENDENT_SHA256_SOURCE_HISTORY \
  --restore-deployments /private-review/restore-deployments.json \
  --restore-deployments-sha256 INDEPENDENT_SHA256_RESTORE_HISTORY \
  --project-id APPROVED_RAILWAY_PROJECT_ID \
  --environment-id APPROVED_RAILWAY_ENVIRONMENT_ID \
  --expected-repo maghsoodsaadatmerikation-sudo/nexus \
  --source-service-id APPROVED_SOURCE_ID \
  --restore-service-id APPROVED_RESTORE_ID \
  --source-volume-id APPROVED_SOURCE_VOLUME_ID \
  --restore-volume-id APPROVED_RESTORE_VOLUME_ID \
  --expected-commit APPROVED_FULL_SHA
\`\`\`

The tool reports \`commit_coherence=BLOCKED\` if either deployed commit differs from the separately approved exact commit, if both services report different revisions, if deployment is sleeping/offline, if volume or running-replica evidence is missing, or if a staged patch remains.

On internally consistent and healthy **synthetic** provider snapshots with the same separately approved revision, the result can be \`SNAPSHOT_CONSISTENT_ONLY\`. That means no more than the pinned metadata agreed: it does **not** certify actual running source bytes, an independent failure domain, an off-host restore, or a compatible private key signer. It never grants release authority: \`release_gate=BLOCKED\` and \`production_release_authorized=false\` are unconditional.

For an explicit release gating integration, invoke the same CLI with \`release-gate\` instead of \`inspect\`; it **always exits nonzero** even for consistent snapshots. A parse/identity/tamper mismatch also exits nonzero on either mode.

Run \`python3 scripts/test-workspace-stage-d-deploy-coherence.py\` for synthetic adversarial tests. The tests don't query Railway. GitHub Actions checks the exact PR commit with no provider credentials, and the mandatory \`readonly-verification.sh\` includes them.

## Known limitations and next operator gates

- A purported Git commit hash in a deployment record is not an attestation that a sleeping/running binary actually matches that source, nor does it prove the deployment built or started correctly.
- The check intentionally requires the exact **same** approved commit across source and restore for a baseline compatibility drill. A future separately audited migration might explicitly support differing but compatible revisions, but this verifier cannot authorize that scenario.
- A signed observer checkpoint, independently pinned current state, durable offsite encrypted backup, an actual destructive recovery on a **separately authorized isolation volume**, read-only HTTPS/authenticated transport checks and release approval are still missing.
- The two existing Railway Stage D services and mounted volumes have not been woken, redeployed, mutated, or used to process customer data. The existing \`STAGED\` provider patch has not been accepted or discarded.

No production or key-cutover action is implemented in this stage.
