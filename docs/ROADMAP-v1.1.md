# NEXUS v1.1 Roadmap

NEXUS v1.1 begins after the immutable `v1.0.0` release boundary. Nothing in this roadmap changes the claims, evidence, tag, or seal attached to v1.0.0.

## Goal

Improve operational resilience and deployment safety without expanding machine epistemic authority.

The constitutional invariant remains:

`A_out <= A_in`

## Stage A — Operational Health

Status: **COMPLETE / VERIFIED**

Implemented:

- container-level Docker health contract;
- health state verified as `healthy` in the production-shaped CI container;
- health re-verified after restart;
- liveness deliberately kept separate from epistemic correctness and authority;
- no secret or evidence payload is exposed by the health check.

Verification basis: NEXUS Verification #251, run `33546980317` — PASS.

## Stage B — Backup and Recovery

Status: **COMPLETE / VERIFIED; BROWSER SAFEGUARD ADDED**

Implemented and verified previously:

- authenticated `scripts/workspace-backup.sh` operator helper;
- validated `scripts/workspace-restore.sh` operator helper;
- JSON syntax validation before local backup acceptance and before restore submission;
- server-side snapshot revalidation remains mandatory on import;
- CI creates a workspace, exports its complete snapshot, destroys the backing data, starts a fresh instance, restores the snapshot, compares restored state with the backup, then restarts again and verifies persistence;
- backup/restore script hashes are included in verification evidence.

Verification basis for the recovery boundary: NEXUS Verification #251, run `33546980317` — PASS.

Additional ephemeral-host safeguard on `main`:

- browser UI now has an explicit **Backup / recovery** section;
- **Download verified backup** first fetches a fresh authenticated server snapshot rather than exporting potentially stale in-memory state;
- the browser checks the minimum snapshot structure before download;
- backup filenames include workspace ID and UTC timestamp;
- restore performs local JSON/structure checks and then submits the snapshot to the existing authenticated `/v1/workspaces/import` boundary for authoritative server-side revalidation;
- the UI explicitly tells operators to store backups independently of an ephemeral host;
- workspace mutations prompt the operator to refresh the backup.

This safeguard reduces data-loss risk on ephemeral hosting. It does not make ephemeral storage durable.

## Stage C — Production Observability

Status: **COMPLETE / VERIFIED**

Implemented:

- redacted lifecycle marker on application startup;
- operational server-exit error marker;
- startup marker reports bind address, data directory, and only `auth=configured`, never the bearer-token value;
- `docs/OBSERVABILITY.md` defines allowed signals, prohibited payload logging, retention/redaction guidance, and the boundary between service health and epistemic correctness;
- CI observes the startup marker on each production-shaped container start and fails if the CI bearer token appears in application logs;
- observability contract hash and PASS state are included in verification evidence.

Verification basis: NEXUS Verification #255, run `33547337891` — PASS.

## Stage D — Durable Production Validation

Status: **HOST CONTRACT + EVIDENCE HARNESS READY / EXTERNAL PROVISIONING REQUIRED**

Prepared:

- `deploy/oci/docker-compose.yml` binds the application to loopback and mounts durable host storage at `/data`;
- `deploy/oci/README.md` defines the OCI persistent-host deployment and the exact Stage D evidence procedure;
- `scripts/stage-d-evidence.sh` provides a provider-agnostic operator harness for pre-replacement capture, post-replacement survival verification, and restore verification;
- Stage D capture binds its evidence to the exact deployed 40-character repository commit;
- `docs/STAGE-D-EVIDENCE.md` defines the evidence protocol, completion criterion, and evidence hygiene;
- the Stage D harness stores snapshot hashes and PASS state but never writes the bearer token into evidence;
- bearer authentication remains fail-closed and secret material is not committed;
- the deployment contract preserves the existing Docker health check and persistent `NEXUS_DATA_DIR` semantics.

Still required as runtime evidence:

- provision a real persistent host/storage resource;
- expose the service through HTTPS while keeping application port 3000 non-public;
- run Stage D `capture` from an operator machine with the evidence directory stored independently of the host;
- perform a real service/container replacement without restoring first;
- pass `verify-survival` against the pre-replacement snapshot;
- execute a separate destructive backup/restore recovery exercise on the host and pass `restore-verify`;
- record deployment evidence separately from release evidence.

The current Render Free deployment remains classified as:

`PUBLIC / AUTHENTICATED / FUNCTIONALLY VALIDATED / EPHEMERAL`

It is not durable production.

## Stage E — Release Readiness Guard

Status: **IMPLEMENTED / FAIL-CLOSED; AWAITS STAGE D EVIDENCE**

Implemented:

- `scripts/v1.1-release-readiness.sh` validates a complete Stage D evidence pack offline;
- the gate requires capture, survival, and restore PASS records to share the exact captured snapshot hash;
- it requires post-replacement and post-restore snapshots to be JSON-equivalent to the captured state;
- it binds the evidence pack to the exact deployed repository commit;
- it rejects missing/incomplete evidence and credential-like material in result records;
- it performs no tag, release, deployment, authorization, or epistemic action;
- `docs/RELEASE-READINESS-v1.1.md` defines the gate and its fail-closed semantics;
- CI must verify that ordinary repository verification cannot accidentally turn missing Stage D runtime evidence into release readiness.

Stage E can be implementation-complete while its release decision remains blocked. `V1.1 RELEASE READINESS: PASS` is permitted only after real Stage D host evidence exists for the exact deployed commit.

## Current v1.1 boundary

Stages A through C are complete and verified. Stage D's repository-side deployment contract and evidence harness are ready but still require a real persistent external host. Stage E now provides a fail-closed release gate so Stage D cannot be bypassed by documentation, CI simulation, or operator assertion alone.

No code, UI, backup download, evidence harness, release-readiness script, or documentation change may convert an ephemeral deployment into a durable-production claim. That claim requires real persistent hosting evidence.

## Release discipline

No `v1.1.0` seal is permitted while Stage D lacks real host evidence or while the Stage E release-readiness gate has not passed against that evidence and the exact deployed commit. Documentation, CI simulation, or an evidence harness alone is not evidence of runtime success.
