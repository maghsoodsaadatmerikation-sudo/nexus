# NEXUS Deployment Contract

This document governs deployment after the sealed `v1.0.0` constitutional/product baseline and incorporates the durable-host evidence boundary sealed in `v1.1.0`. Both release tags remain immutable historical boundaries.

## Required runtime inputs

NEXUS fails closed if `NEXUS_API_TOKEN` is missing or empty.

Required:

- `NEXUS_API_TOKEN` — bearer token required for authenticated workspace routes.

Optional:

- `NEXUS_DATA_DIR` — durable workspace directory. Default outside the container is `nexus-data`; the production container sets `/data`.
- `NEXUS_BIND_ADDR` — socket address. Local default is `127.0.0.1:3000`; the production container sets `0.0.0.0:3000`.

The data directory must be mounted on durable storage in any real deployment. An ephemeral filesystem is not an acceptable durable-production configuration because DecisionWorkspace persistence is part of the verified product contract.

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

## Release discipline

The sealed `v1.0.0` and `v1.1.0` tags must not be moved. Later commits require their own CI evidence, and any future release must establish evidence appropriate to its new claims before it is sealed.
