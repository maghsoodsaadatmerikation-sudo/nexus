# Stage D Railway: read-only provider health and topology preflight

## Purpose

\`scripts/workspace-stage-d-railway-preflight.py\` examines **two previously exported, untrusted, exact-SHA-256-pinned JSON snapshots** of the NEXUS Railway environment: the inventory from \`Railway.describe_environment\` and runtime status from \`Railway.environment_status(includeSuccessful=true)\`.

It does **not** contact Railway, send network requests, wake sleeping services, deploy, edit health checks, accept staged patches, read private volumes, copy data, repair a service, or make an authorization decision. It intentionally distinguishes (a) separate service/volume IDs on the same provider, (b) an actually online deployment of each service, and (c) separately authenticated organizational independence and a real off-host restore. A green provider snapshot can establish **only** (a) and part of (b), never (c).

A prior NEXUS stage created a read-only cryptographic drill auditor in \`scripts/workspace-witness-drill-audit.py\`. That auditor verifies signed history, the cold backup, two observer signatures and consumed nonce. This provider-topology review is a **separate prerequisite**, not proof that the signed drill has actually run on different machines. The results must be reconciled by a human operator before any real release approval.

## Read-only actual provider findings, 15 November 2026

Inspection of the connected Railway project \`NEXUS Stage D\` found:

| Resource | Source service | Recovery service |
|---|---|---|
| Service | \`nexus-stage-d\` | \`nexus-stage-d-restore\` |
| Region | \`sfo\` | \`us-west2\` |
| Declared mount | separate \`/data\` volume | separate \`/data\` volume |
| Runtime/deployment state | \`sleeping\` / \`SLEEPING\` | \`sleeping\` / \`SLEEPING\` |
| Verified running replicas | not established | not established |

The separate \`stage-d-runner\` is offline with last known deployment \`FAILED\`; one operator is online, another is offline. There is **an unapplied staged patch** for the source service's health-check path (\`/\` to \`/readyz\`), along with a no-value-change sleep setting. No staged patch was committed or discarded.

These are **metadata observations**, not a proof of valid on-volume backup, exact common deployed commit, external encrypted custody, healthy HTTPS, independent operators, independent failure domains, or a successful restore after actual destruction. The existing Render NEXUS production service is a separate provider and is likewise **not** changed.

## Offline operator input and procedure

From the connected Railway application, collect provider-native responses to \`describe_environment\` and \`environment_status\` for the **same selected project and environment**. Export each response to a separate unchanged JSON file **outside** the staging/production data volumes. Retain the exact file bytes' SHA-256 in a separately controlled reviewer ledger. Provider JSON must not contain secret variables; do not export provider secrets, HTTP authorization headers or private keys. The CLI rejects ambiguous JSON and unsafe symlink/hardlink inputs.

Use operator-approved exact IDs: project, environment, original service, recovery service, original mounted volume, recovery mounted volume and exact repository path (e.g. \`maghsoodsaadatmerikation-sudo/nexus\`). These IDs cannot be derived solely from the snapshot being evaluated and called independently trusted.

\`\`\`sh
python3 scripts/workspace-stage-d-railway-preflight.py inspect \
  --inventory /review/railway-environment-inventory.json \
  --inventory-sha256 INDEPENDENT_EXACT_INVENTORY_SHA256 \
  --health /review/railway-environment-health.json \
  --health-sha256 INDEPENDENT_EXACT_HEALTH_SHA256 \
  --project-id OPERATOR_APPROVED_RAILWAY_PROJECT_ID \
  --environment-id OPERATOR_APPROVED_ENVIRONMENT_ID \
  --expected-repo maghsoodsaadatmerikation-sudo/nexus \
  --source-service-id APPROVED_SOURCE_SERVICE_ID \
  --restore-service-id APPROVED_RESTORE_SERVICE_ID \
  --source-volume-id APPROVED_SOURCE_VOLUME_ID \
  --restore-volume-id APPROVED_RESTORE_VOLUME_ID
\`\`\`

The tool requires two *distinct* service IDs with distinct mounted \`/data\` volume IDs; cross-checks source repository, project and environment, volume ownership/region, service identity, provider runtime state, active and latest deployment status, running replica count, staged patch and pending operations.

If both services appear to be live, online with exactly one successful matching active deployment and at least one verified running replica, with distinct reported regions and **no staged environment patch**, the response is \`online_topology_preflight=SNAPSHOT_CONSISTENT_ONLY\`. This still does not prove provider signatures, availability at the present moment, a different failure domain, a current deployed Git commit or any actual remote restore.

Any sleeping, offline, failed or stale deployment, missing replica, same reported region or unapplied patch returns \`online_topology_preflight=BLOCKED\` with explicit \`blocked_reasons\`. A structurally inconsistent/unpinned snapshot exits nonzero. This prevents Railway's top-level \`hasIssues=false\` from being mistaken for proof that a sleeping witness is actually online.

The separate \`release-gate\` subcommand accepts the same arguments, **always** prints \`release_gate=BLOCKED\`, \`production_release_authorized=false\` and exits nonzero. This stage cannot grant production authority, no matter what the provider reported.

## Verification and limits

Run \`python3 scripts/test-workspace-stage-d-railway-preflight.py\`, or check the dedicated GitHub Actions workflow. These tests use only **synthetic snapshots**, not the current connected Railway responses or live machines.

This operator preflight should be completed and independently reviewed before any potentially disruptive action on real Railway services. The required next independent evidence includes live signed response from each distinct host, exact committed Git revision deployed on both, an externally approved 256-bit challenge, independent custody of encrypted backups, an observed destructive restore in an isolated recovery environment, and provider/operator attestation. No real two-host recovery has yet been performed or implied.

Never accept an \`inspect\` exit code 0 as permission to release. Review \`online_topology_preflight\`, the release denial flags and all independent Stage D gates separately.
