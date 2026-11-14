# NEXUS Deployment Contract

This document governs deployment after the sealed `v1.0.0` constitutional/product baseline and incorporates the durable-host evidence boundary sealed in `v1.1.0`. Both release tags remain immutable historical boundaries.

## Required runtime inputs

NEXUS fails closed if `NEXUS_API_TOKEN` is missing, empty, or contains whitespace, non-ASCII or non-printable bytes. Use a long, random **printable ASCII token without spaces**, and keep it out of source, browser assets and logs.

Required:

- `NEXUS_API_TOKEN` — bearer token for authenticated Workspace **and request** API routes; only one unambiguous `Authorization: Bearer ...` header is accepted.

Optional:

- `NEXUS_DATA_DIR` — durable workspace directory. Default outside the container is `nexus-data`; the production container sets `/data`.
- `NEXUS_BIND_ADDR` — socket address. Local default is `127.0.0.1:3000`; the production container sets `0.0.0.0:3000`.
- `NEXUS_EXPECTED_VOLUME_ID` — **opt-in, strongly recommended before production admission**. Exactly 32 lowercase hexadecimal characters naming the pre-enrolled persistent data volume. When configured, NEXUS validates `/data/.nexus-volume-identity` **before any data-directory creation** and again after storage handles initialize. Missing, malformed, symlinked, hardlinked or mismatched identity blocks startup without trying to create or repair a replacement volume. A missing setting retains legacy startup for compatibility; legacy mode does **not** protect against an empty replacement volume after a full process restart.

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
- `workspace_unavailable` — the pinned Workspace root is unavailable/replaced, or the configured volume marker is lost/mismatched
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

## Durable-volume identity: new installs versus existing data

**New empty offline volume only:** after creating a physically separate and
empty durable directory, generate an unpredictable non-secret volume ID, then
enroll it explicitly **while all gateway writers are stopped**. The enrollment
command is in the repository's operator scripts, not inside the runtime
container image.

```sh
# Commands run on a trusted operator host with the real volume mounted;
# do NOT run on an unrecognized replacement or an existing populated volume.
VOLUME_ID="$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
python3 scripts/enroll-new-volume.py /path/to/NEW-EMPTY-data-volume \
  --volume-id "$VOLUME_ID" --offline \
  --confirm 'I AM INITIALIZING A NEW EMPTY NEXUS DATA VOLUME'
# Configure the same VOLUME_ID privately as NEXUS_EXPECTED_VOLUME_ID
# in the gateway environment, and preserve it in protected recovery records.
```

A startup without this ID remains backward-compatible but cannot detect a
lost original volume followed by startup on a new blank directory.
**Never enroll a newly presented empty disk during an incident** simply to
recover readiness; halt, locate the original volume or perform an independently
verified full-data restore first. Existing populated volumes cannot be
enrolled by the new-volume script: migration requires verified off-host
backup, stopped writers, a separately reviewed offline enrollment procedure,
and a restore rehearsal. No command in this repository automatically upgrades
an existing production volume.

The identity marker is copied into full-volume snapshots and preserved by
isolated restore along with Workspace snapshots and the request ledger; the
restore still creates the recovery quarantine marker. The volume ID is **not
authentication**, a disk hardware serial, a cryptographic signature, an
independent custody receipt, or permission to dismiss quarantine. A root can
still be tampered with by actors who can rewrite both the volume and marker.
When configured, the original marker and pinned root are rechecked on **every
`/readyz` probe and authenticated private Workspace/request API operation**.
Removing or changing the marker after startup changes `/readyz` to HTTP
**503** `workspace_unavailable`, and private routes reject requests with
HTTP **503** `volume_identity_unavailable` before parsing their bodies or
reserving request IDs. `/livez` remains 200, avoiding recovery restart loops;
invalid bearer credentials receive 401 before the storage state is disclosed.
Restoring the exact original marker can recover readiness without a restart
provided other storage and recovery gates pass.

These are discrete checks, **not an atomic lock across a complete API
transaction**: a hostile concurrent marker edit after the check can still race
an in-flight operation. This is not continuous cryptographic integrity, a
substitute for correctly isolated provider permissions, or proof that future
disk writes and fsyncs will succeed.

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
