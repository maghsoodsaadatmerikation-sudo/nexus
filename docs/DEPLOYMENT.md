# NEXUS Deployment Contract

This document applies to development after the sealed `v1.0.0` release. The release tag remains an immutable historical boundary; deployment work happens on later commits.

## Required runtime inputs

NEXUS fails closed if `NEXUS_API_TOKEN` is missing or empty.

Required:

- `NEXUS_API_TOKEN` — bearer token required for authenticated workspace routes.

Optional:

- `NEXUS_DATA_DIR` — durable workspace directory. Default outside the container is `nexus-data`; the production container sets `/data`.
- `NEXUS_BIND_ADDR` — socket address. Local default is `127.0.0.1:3000`; the production container sets `0.0.0.0:3000`.

The data directory must be mounted on durable storage in any real deployment. An ephemeral filesystem is not an acceptable production configuration because DecisionWorkspace persistence is part of the verified product contract.

## Build

The repository includes a Dockerfile whose Rust builder/runtime image is pinned to the same digest used by verification.

```sh
docker build -t nexus:post-v1 .
```

The build uses the committed Artifact 05 lockfile with `--locked` and fails if dependency resolution would change.

## Run locally in a production-shaped container

```sh
mkdir -p nexus-data

docker run --rm \
  -p 3000:3000 \
  -e NEXUS_API_TOKEN='replace-with-a-long-random-secret' \
  -v "$PWD/nexus-data:/data" \
  nexus:post-v1
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
4. Restart-on-failure semantics without discarding `/data`.
5. No public exposure of the bearer token in build logs, image layers, repository files, or browser source.

The browser currently asks the operator for the bearer token at runtime and holds it only in page memory. Do not hard-code a production token into `web/index.html`.

## Security boundary

Authentication is a transport/product boundary, not epistemic authority. A valid bearer token permits access to workspace routes; it does not grant the gateway authority to create HumanJudgment, bypass PolicyEngine, reinterpret evidence, or mutate constitutional policy.

## Import/export

Exported workspace JSON is evidence-bearing state. Import is revalidated through `WorkspaceEngine::from_snapshot` before persistence. Invalid sequence histories and unsupported snapshots fail closed.

Back up the mounted data volume independently of JSON exports. Exports are useful portability/audit artifacts but are not a substitute for durable operational backups.

## Release discipline

The sealed `v1.0.0` tag points to commit `50b27c252de6d5a38eb6958b7e31ba7fe66f5545` and must not be moved. Post-release commits require their own CI evidence before any later release is sealed.
