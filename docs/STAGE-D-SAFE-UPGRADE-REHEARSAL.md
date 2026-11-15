# NEXUS Stage D — non-executing safe version alignment and rollback rehearsal

## Why this step exists

Read-only Railway deployment-history metadata recorded on 15 November 2026 showed:

| Component | Reported latest source Git SHA | State |
|---|---|---|
| \`nexus-stage-d\` (original, \`sfo\`) | \`9abbc067aad3ebbb0956432cf6682d2ea70e2824\` | \`SLEEPING\` |
| \`nexus-stage-d-restore\` (recovery, \`us-west2\`) | \`588dc7672146031425b16b34956876d644244ace\` | \`SLEEPING\` |
| \`main\` (repository reference at inspection) | \`f4d027bb5f7e715b298f7cf7184fa621a2fb071d\` | not a deployed Stage D runtime |

Read-only GitHub commit comparisons showed the recovery commit to be an ancestor **139 commits** behind the source deployed commit. The source deployed commit was an ancestor **40 commits** behind the repository's then-current \`main\`. This is **historical ancestry**, not proof of schema compatibility, secure backup, production readiness or successful rollback. The actual source and recovery service versions are not identical.

Railway also showed a non-applied health-check patch and a non-running Stage D runner. These observations were made without waking services, committing the patch, changing a volume or provisioning resources. No claim of readiness is made.

## Scope of this PR

\`scripts/workspace-stage-d-upgrade-rehearsal.py\` is an **offline review tool, not an execution engine**. It cross-checks:
1. Independently SHA-256-pinned Railway inventory, runtime health, source deployment history and recovery deployment history;
2. Independently SHA-256-pinned GitHub \`compare_commits\` outputs, binding \`restore_current_commit → source_current_commit\` and \`source_current_commit → proposed_rehearsal_commit\`. Each must report the exact approved repository and endpoints, direct ancestry with merge base equal to the earlier commit, a coherent nonnegative ahead/behind count and no divergence or truncation;
3. A strict, independently SHA-256-pinned operator plan, binding precisely the *observed* deployed original and recovery commit SHA, both pre-rehearsal code fallbacks, source/restore service and volume IDs, repository, project and environment.

A proposed target can be the currently deployed source version for an **isolated** recovery compatibility rehearsal or a later reviewed commit on the same Git path. This tool does not decide which source version is suitable for real data, and its output does **not** authorize changing either existing service.

### Non-executable plan schema

Save a canonical JSON object containing exactly these fields and value constraints. The real IDs and revisions must come from independently reviewed provider and GitHub evidence.

\`\`\`json
{
  "schema": "nexus.stage-d.nonexecuting-upgrade-rehearsal.v1",
  "project_id": "APPROVED_RAILWAY_PROJECT",
  "environment_id": "APPROVED_RAILWAY_ENVIRONMENT",
  "repository": "maghsoodsaadatmerikation-sudo/nexus",
  "source_service_id": "APPROVED_ORIGINAL_SERVICE",
  "restore_service_id": "APPROVED_RECOVERY_SERVICE",
  "source_volume_id": "APPROVED_ORIGINAL_VOLUME",
  "restore_volume_id": "APPROVED_RECOVERY_VOLUME",
  "source_current_commit": "9abbc067aad3ebbb0956432cf6682d2ea70e2824",
  "restore_current_commit": "588dc7672146031425b16b34956876d644244ace",
  "proposed_rehearsal_commit": "9abbc067aad3ebbb0956432cf6682d2ea70e2824",
  "source_fallback_commit": "9abbc067aad3ebbb0956432cf6682d2ea70e2824",
  "restore_fallback_commit": "588dc7672146031425b16b34956876d644244ace",
  "run_mode": "review-only",
  "destination_policy": "new-disposable-isolated-volume",
  "permit_source_volume_write": false,
  "permit_restore_volume_write": false,
  "permit_destructive_test": false,
  "permit_apply_provider_patch": false,
  "permit_deploy_or_wake": false,
  "permit_signer_rotation": false,
  "require_independent_backup_and_checkpoint": true,
  "require_data_schema_rollback_review": true
}
\`\`\`

The tool fails closed if any live-volume write, destructive action, provider patch acceptance, deployment, service wake or signer rotation is permitted by the input. It requires both code fallback revisions to be exactly the originally observed deployed versions. **Code fallback is not data rollback**: a schema migration, altered persisted file layout or loss of keys may prevent restoring previous code safely. The tool never writes a deployment command, updates a Railway resource or performs a rollback itself.

### Invocation

Collect and independently retain SHA-256 for these seven JSON evidence inputs:
- \`--inventory\` and \`--inventory-sha256\`
- \`--health\` and \`--health-sha256\`
- \`--source-deployments\` and \`--source-deployments-sha256\`
- \`--restore-deployments\` and \`--restore-deployments-sha256\`
- \`--restore-to-source\` and \`--restore-to-source-sha256\`
- \`--source-to-target\` and \`--source-to-target-sha256\`
- \`--plan\` and \`--plan-sha256\`

The first four are read-only responses from Railway connector actions; the two comparisons are read-only responses from GitHub \`compare_commits\`. All seven can be inspected using the actual operator-approved project, repository and release identifiers. The value in \`--source-to-target\` must be a comparison with \`base=source_current_commit\` and \`head=proposed_rehearsal_commit\`; a target equal to source requires a genuine \`identical\` comparison with zero commits.

\`\`\`sh
python3 scripts/workspace-stage-d-upgrade-rehearsal.py inspect \
  --inventory /private-review/railway-inventory.json \
  --inventory-sha256 PIN_INVENTORY \
  --health /private-review/railway-health.json \
  --health-sha256 PIN_HEALTH \
  --source-deployments /private-review/source-deployments.json \
  --source-deployments-sha256 PIN_SOURCE_DEPLOYS \
  --restore-deployments /private-review/restore-deployments.json \
  --restore-deployments-sha256 PIN_RESTORE_DEPLOYS \
  --restore-to-source /private-review/git-restore-to-source.json \
  --restore-to-source-sha256 PIN_GIT_ANCESTRY_1 \
  --source-to-target /private-review/git-source-to-target.json \
  --source-to-target-sha256 PIN_GIT_ANCESTRY_2 \
  --plan /private-review/operator-rehearsal-plan.json \
  --plan-sha256 PIN_PLAN \
  --project-id APPROVED_PROJECT \
  --environment-id APPROVED_ENVIRONMENT \
  --expected-repo maghsoodsaadatmerikation-sudo/nexus \
  --source-service-id APPROVED_SOURCE \
  --restore-service-id APPROVED_RESTORE \
  --source-volume-id APPROVED_SOURCE_VOLUME \
  --restore-volume-id APPROVED_RESTORE_VOLUME
\`\`\`

The \`inspect\` command returns zero only for a **well-formed, internally consistent, non-executable review**. It ALWAYS reports \`release_gate=BLOCKED\`, \`provider_release_authorized=false\`, \`actual_rehearsal_executed=false\`, and \`real_rollback_tested=false\`. An observer should review the \`blocked_reasons\` and \`rehearsal_order\` before planning any real action.

\`release-gate\` takes the same flags and **always exits nonzero**, including if the provider inventory appears entirely healthy and both Git graphs are direct ancestors.

## Safe sequence for a separately approved future physical rehearsal

Before touching a real provider:
1. Establish a **separately retained immutable, encrypted off-host backup** and independent current state hash and monotonic sequence checkpoint; verify restorability away from the live volumes.
2. Confirm compatible binary/schema/protocol versions for the proposed target and historical rollback revisions by explicit tests on a non-sensitive disposable snapshot; never assume a Git ancestor can read a newer data schema.
3. Only after separate operator approval, provision an isolated disposable recovery target with a separately approved cost ceiling. **Never** attach or overwrite the existing source/restore \`/data\` volumes for the rehearsal.
4. Start the isolated service with explicit immutable image digest, limited privileges, withheld production signing keys, and reviewed network isolation. Verify data, witness signatures, off-host monotonic sequence and one-time nonce proofs, recording each stage's exact checksums and provenance.
5. Inject failure **only** in the isolated disposable environment and verify recovery from the independently pinned cold backup. Do not use destructive tests on existing Railway source or recovery volumes.
6. If anything deviates, fail closed, preserve forensic evidence and original snapshots; no automatic mutation, data rollback, live code deploy, signer rotation or patch acceptance is allowed.

This PR implements **only** the signed metadata validation and operator-review plan, not these live actions.

## Testing

\`python3 scripts/test-workspace-stage-d-upgrade-rehearsal.py\` uses entirely synthetic Railway and GitHub JSON fixtures and hostile mutations to verify direct Git history, exact pinned original releases, immutable volume policy, and fail-closed semantics. Dedicated GitHub Actions checks the exact PR commit without provider credentials; \`scripts/readonly-verification.sh\` also requires the test.

Unresolved real-world blockers include Stage D services being \`SLEEPING\`, a pending provider patch, no verified independently custodied backup, a non-operational runner, no verified current runtime code attestation and no observed destructive recovery on a separate disposable host. No claim of end-to-end real-world readiness or cost-free hosted testing is made.
