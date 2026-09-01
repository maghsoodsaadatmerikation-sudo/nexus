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

Status: **COMPLETE / VERIFIED**

Implemented:

- authenticated `scripts/workspace-backup.sh` operator helper;
- validated `scripts/workspace-restore.sh` operator helper;
- JSON syntax validation before local backup acceptance and before restore submission;
- server-side snapshot revalidation remains mandatory on import;
- CI creates a workspace, exports its complete snapshot, destroys the backing data, starts a fresh instance, restores the snapshot, compares restored state with the backup, then restarts again and verifies persistence;
- backup/restore script hashes are included in verification evidence.

Verification basis: NEXUS Verification #251, run `33546980317` — PASS.

## Stage C — Production Observability

Status: **IN PROGRESS**

Objectives:

- operational startup/failure signals that do not leak bearer tokens or evidence payloads;
- startup/restart visibility;
- health and failure signals separated from epistemic claims;
- documented retention and redaction rules.

Exit criterion: operators can detect service startup/failure without turning monitoring output into epistemic authority or exposing user evidence.

## Stage D — Durable Production Validation

Status: **BLOCKED ON DURABLE STORAGE**

Objectives:

- deploy with persistent storage;
- survive a real host/service restart or replacement;
- verify backup/recovery;
- verify fail-closed bearer authentication and HTTPS;
- record deployment evidence separately from release evidence.

The current Render Free deployment remains classified as:

`PUBLIC / AUTHENTICATED / FUNCTIONALLY VALIDATED / EPHEMERAL`

It is not durable production.

## Release discipline

No `v1.1.0` seal is permitted until all claimed stages have real verification evidence. Documentation alone is not evidence of runtime success.
