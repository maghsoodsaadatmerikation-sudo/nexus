# NEXUS Deployment Contract

This document governs deployment after the sealed `v1.0.0` constitutional/product baseline and incorporates the durable-host evidence boundary sealed in `v1.1.0`. Both release tags remain immutable historical boundaries.

## Required runtime inputs

NEXUS fails closed if `NEXUS_API_TOKEN` is missing, empty, or contains whitespace, non-ASCII or non-printable bytes. Use a long, random **printable ASCII token without spaces**, and keep it out of source, browser assets and logs.

Required:

- `NEXUS_API_TOKEN` — bearer token for authenticated Workspace **and request** API routes; only one unambiguous `Authorization: Bearer ...` header is accepted.

Optional:

- `NEXUS_DATA_DIR` — durable workspace directory. Default outside the container is `nexus-data`; the production container sets `/data`.
- `NEXUS_BIND_ADDR` — socket address. Local default is `127.0.0.1:3000`; the production container sets `0.0.0.0:3000`.

The data directory must be mounted on durable storage in any real deployment. The gateway uses the configured root for Workspace snapshots and the `requests/` ledger subdirectory. It pins the Workspace directory and the request ledger identity for its lifetime; a replaced or missing directory is an outage, **not** permission to initialize empty history. An ephemeral filesystem is not an acceptable durable-production configuration because DecisionWorkspace persistence is part of the verified product contract.

## Build

The repository includes a Dockerfile whose Rust builder/runtime image is digest-pinned and whose dependency resolution is locked.

```sh
docker build -t nexus:v1.1 .
```

The build uses the committed Artifact 05 lockfile with `--locked` and fails if dependency resolution would change.

## Run locally in a production-shaped container

```sh
mkdir -p nexus-data

docker run --rm \
  -p 3000:3000 \
  -e NEXUS_API_TOKEN='replace-with-a-long-random-secret' \
  -v "$PWD/nexus-data:/data" \
  nexus:v1.1
```

Open `http://127.0.0.1:3000/` for the browser client. Workspace API requests must provide:

```text
Authorization: Bearer <NEXUS_API_TOKEN>
```

## Liveness and readiness

The current gateway exposes two **public, read-only** checks with
`Cache-Control: no-store`: `/livez` returns 200 with
`{"status":"alive"}` when the listener responds, even in recovery quarantine.
`/readyz` returns 200 with `{"status":"ready"}` only when its configured
startup recovery, request-ledger identity, Workspace root identity, and permanent
tracked-request capacity checks pass. Otherwise it returns HTTP **503** with
one of these exact status strings:

- `quarantined` — the startup recovery gate is latched
- `storage_unavailable` — the durable request ledger is unavailable/replaced
- `workspace_unavailable` — the pinned Workspace root is unavailable/replaced
- `admission_unavailable` — the permanent tracked-request budget is exhausted

The Workspace API also distinguishes a storage I/O outage with HTTP **503**
`workspace_storage_unavailable` from an invalid workspace request (422),
and duplicate Workspace creation/import returns HTTP **409**
`workspace_already_exists`.

Use `/readyz` for admission monitoring and `/livez` for liveness; the
container Docker HEALTHCHECK intentionally invokes
`/usr/local/bin/nexus --health-check`, which checks **liveness**, to avoid
restart loops during recovery quarantine. The Render Blueprint uses the root
path `/` as a health check; that route is **not** a readiness guarantee.
A successful `/readyz` check is read-only and **cannot prove disk writability,
absence of ENOSPC, the next fsync, full historical integrity, authorization,
or successful recovery**. See [the exact probe contract](gateway-health.md).

## Production requirements

A hosting platform is acceptable only if it can provide all of the following:

1. A private secret environment variable for `NEXUS_API_TOKEN`.
2. A persistent volume mounted at `/data`.
3. Inbound HTTPS terminating in front of port `3000`.
4. Restart/replacement semantics that preserve `/data`.
5. No public exposure of the bearer token in build logs, image layers, repository files, evidence files, or browser source.
6. A lifecycle path that can be independently exercised for capture, replacement survival, destructive absence, and restore.

The browser asks the operator for the bearer token at runtime and holds it only in page memory. Do not hard-code a production token into `web/index.html`.

## Security boundary

Authentication is a transport/product boundary, not epistemic authority. A valid bearer token permits access to workspace routes; it does not grant the gateway authority to create HumanJudgment, bypass PolicyEngine, reinterpret evidence, or mutate constitutional policy.

## Import/export and recovery

Exported workspace JSON is evidence-bearing state. Import is revalidated through `WorkspaceEngine::from_snapshot` before persistence. Invalid sequence histories and unsupported snapshots fail closed.

Back up the mounted data volume independently of JSON exports. Exports are useful portability/audit artifacts but are not a substitute for durable operational backups.

The v1.1 durable-host verification exercised the release protocol in `docs/STAGE-D-EVIDENCE.md`: authenticated capture, real service replacement, survival verification, destructive backing-state absence, and restore verification. Passing that exercise establishes observed behavior for the tested deployment and lifecycle only; it does not imply general availability, load, or disaster-recovery guarantees.

## Sealed durable-host boundary

`v1.1.0` is sealed to deployed commit:

```text
480f8771c47e41d4d19b22ed4360bd32c4d2f70a
```

Associated exact-commit NEXUS Verification run:

```text
34824938788 — SUCCESS
```

The durable-host witness snapshot was bound to SHA-256:

```text
71271177cadc1dd67afdf0ddbc913c89c54b326df66bdb2f1dd803da94107d7b
```

## Release discipline and current deployment hold

The sealed `v1.0.0` and `v1.1.0` tags must not be moved. Later commits require their own CI evidence, and any future release must establish evidence appropriate to its new claims before it is sealed.

**Live-control observation (2026-11-14; refresh before acting):** the existing
Render service `nexus` is configured to auto-deploy commits from `main`.
The GitHub default-branch ruleset `Merikation` does not currently enforce
strict up-to-date required status checks. This repository's `render.yaml`
describes a **different proposed service** and does not override the existing
service's live settings. A draft PR with passing CI is **not** permission to
merge into `main` or publish a build.

Before merging or deploying a new candidate, the authorized operator must
disable the existing Render service's auto-deploy, enable strict current-base
GitHub required checks, independently verify both settings, and obtain a
real, encrypted, independently witnessed **full-volume** off-host backup and
isolated cold restore of both Workspace history and request ledger.
The automated cross-runner test transfers only synthetic data and cannot
substitute for real independent recovery evidence. Follow
[the fail-closed freeze preflight](PRODUCTION-FREEZE-PREFLIGHT.md) and
[the synthetic cross-runner recovery limits](PILOT-CROSS-RUNNER-RECOVERY.md).
The current consolidated candidate remains **draft and unmerged**.
