# NEXUS Post-v1 Live Validation Record

Status: **PASS WITH DEPLOYMENT LIMITATION**

Date: 2026-09-01
Environment: Render free web service, public HTTPS endpoint
Source branch: `main`
Validated post-v1 implementation baseline: commit `8b0e4cfe2eff4af1739f4456f816dbcb641d6867`
Pre-deployment CI evidence: NEXUS Verification #243, run `33543321548` — PASS
Latest browser-backup implementation verification: NEXUS Verification #261, run `33548720624` — PASS

## Purpose

This record documents live, operator-observed validation of the post-v1 NEXUS deployment. It does not modify, replace, or extend the sealed `v1.0.0` release boundary.

## Observed live checks

The public deployment was observed to:

1. Build and start the repository Docker image successfully.
2. Bind and expose HTTP port `3000` through the hosting platform.
3. Serve the NEXUS browser workspace over the platform HTTPS endpoint.
4. Accept the operator-held bearer token without placing that token in this repository or this record.
5. Create an authenticated workspace with a generated workspace identifier and schema v1 state.
6. Materialize audit event `#0 WorkspaceCreated`.
7. Add the human-origin claim: `Public Render deployment successfully created an authenticated NEXUS workspace.`
8. Materialize audit event `#1 Claim Added` using source/provenance identifier `production-validation-001`.
9. Record the explicit human decision: `Proceed with post-release production validation.`
10. Materialize audit event `#2 Human Judgment Transition`.
11. Reject an unauthenticated workspace-creation request with `workspace_authentication_required`, confirming fail-closed behavior at the live workspace boundary.
12. Accept a fresh authenticated workspace-creation request after the unauthenticated control test.
13. Download a fresh server-derived browser backup through the **Download verified backup** control.
14. Produce a schema v1 snapshot containing the workspace state and audit event `#0 WorkspaceCreated` without embedding the bearer token or authorization secret.

The earlier observed event order was:

```text
#0 WorkspaceCreated
#1 Claim Added
#2 Human Judgment Transition
```

The later backup-control snapshot independently preserved a fresh workspace with schema v1 state and its `WorkspaceCreated` audit event.

These live checks confirm that the deployed browser/gateway/core path can preserve the explicit distinction between evidence-bearing state and a human judgment transition under authenticated use, fail closed when workspace authentication is absent, and export a server-fresh operator backup without placing the API secret in the snapshot.

## Epistemic scope

This live session directly exercised an explicit human judgment transition. It did **not** exercise a machine-analysis adapter attempting to create HumanJudgment. The prohibition on implicit machine-to-human-judgment promotion remains established by the code boundary and automated verification; this live record does not claim more than was directly observed.

The browser-backup check establishes snapshot export and secret omission for the observed snapshot. It does **not** by itself establish recovery after external host data loss; authoritative restore remains a server-side import/revalidation operation and is separately exercised in CI.

## What this validation does not prove

This record deliberately does **not** claim:

- durable production persistence on the Render free instance;
- availability, latency, load, disaster-recovery, or multi-user guarantees;
- survival of workspace state after host replacement or free-instance filesystem reset;
- a completed destructive live restore-after-loss test on the Render free instance;
- independent external certification of the live endpoint;
- that a public deployment or downloadable backup changes the constitutional authority boundary.

## Storage limitation

The validation instance uses a Render free web service. The free service does not provide the persistent disk required by `docs/DEPLOYMENT.md`. Its workspace filesystem must therefore be treated as **ephemeral**.

For this reason the live instance is classified as:

**PUBLIC / AUTHENTICATED / FUNCTIONALLY VALIDATED / EPHEMERAL**

and not as durable production.

The repository's container verification separately exercises persistence across container restart with a mounted volume. The backup/recovery CI additionally creates a workspace, exports its snapshot, destroys the backing data, starts a fresh instance, restores the snapshot through authenticated server-side import, compares restored state with the backup, and then verifies persistence after another restart. Those CI results do not convert the external Render Free filesystem into durable storage.

## Security note

The bearer token used during validation is intentionally omitted. Secrets must remain outside repository history, release notes, evidence documents, browser source, downloadable snapshots, and public logs.

The observed browser backup did not contain the operator bearer token or an authorization header value.

## Durable-production exit criterion

A future deployment may be classified as durable production only after all of the following are evidenced:

- persistent storage is mounted for `NEXUS_DATA_DIR`;
- a workspace survives a real service restart/replacement using that persistent storage;
- bearer authentication remains fail-closed;
- HTTPS remains enabled;
- backup/recovery behavior is defined and tested;
- the deployment commit has a successful NEXUS verification run.

## Evidence chain

The implementation deployed for the original validation had already passed NEXUS Verification #243 before live deployment, including core verification, self-audit, Artifact 05 Gates 0–3, container smoke testing, durable restart testing with a mounted volume, evidence bundling, and attestation.

The browser backup/recovery safeguard subsequently passed NEXUS Verification #261 on commit `1cf21f2ae81b61bba285f631cd3d0561e26e42cf`. The operator-observed public deployment then demonstrated the unauthenticated control response, authenticated workspace creation, and secret-free schema v1 backup export described above.

The live validation adds deployment-path evidence; it does not weaken or rewrite the earlier CI evidence.

## Conclusion

**PASS WITH DEPLOYMENT LIMITATION.**

The post-v1 NEXUS implementation has been exercised successfully through a real public HTTPS deployment, authenticated human workflow, fail-closed unauthenticated control, and browser-based secret-free backup export. Durable-production status remains intentionally unclaimed until persistent hosting storage is available and validated.