# NEXUS v1.1 Roadmap

NEXUS v1.1 begins after the immutable `v1.0.0` release boundary. Nothing in this roadmap changes the claims, evidence, tag, or seal attached to v1.0.0.

## Goal

Improve operational resilience and deployment safety without expanding machine epistemic authority.

The constitutional invariant remains:

`A_out <= A_in`

## Stage A — Operational Health

Status: IN PROGRESS

Objectives:

- define a container-level health contract;
- verify the health contract in CI against the production-shaped container;
- distinguish liveness/availability signals from epistemic correctness;
- avoid exposing secrets or internal authority state through health checks.

Exit criterion: the production container reports `healthy` under the same CI path that already verifies authenticated workspace creation and durable restart.

## Stage B — Backup and Recovery

Status: PLANNED

Objectives:

- define a portable backup artifact for workspace state;
- preserve schema version, provenance, uncertainty, audit history, and explicit human judgment transitions;
- validate backup import before persistence;
- provide an operator workflow suitable for ephemeral hosting;
- prevent backup/restore from bypassing append-only history validation.

Exit criterion: an exported validated snapshot can be restored into a fresh instance and replay-validates to the same epistemic state.

## Stage C — Production Observability

Status: PLANNED

Objectives:

- operational metrics/logging that do not leak bearer tokens or evidence payloads;
- startup/restart visibility;
- health and failure signals separated from epistemic claims;
- documented retention and redaction rules.

Exit criterion: operators can detect service failures without turning monitoring output into epistemic authority.

## Stage D — Durable Production Validation

Status: BLOCKED ON DURABLE STORAGE

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
