# NEXUS

**Constitutional infrastructure for human judgment.**

NEXUS is a Rust-based constitutional core, epistemic workspace, authenticated HTTP gateway, browser client, and verification pipeline designed to help humans examine questions, evidence, alternatives, uncertainty, and consequences without transferring meaning, identity, or final decision authority to a machine.

## Core principle

> **NEXUS may assist judgment; NEXUS must not own judgment.**

The system separates:

- **Human authority** — values, identity, and final judgment remain human-owned.
- **Evidence** — claims retain explicit provenance and uncertainty.
- **Machine analysis** — research/challenge outputs remain non-authoritative epistemic objects and are never silently promoted to human judgment.
- **Execution authority** — execution remains behind the constitutional authorization boundary.
- **Auditability** — workspace transitions are persisted and replay-validated; release claims are tied to reproducible CI evidence.

## v1.0.0 status

`v1.0.0` is the first sealed production baseline.

- Stage A — Constitutional Foundation: COMPLETE / VERIFIED
- Stage B — Epistemic Engine: COMPLETE / VERIFIED
- Stage C — Gateway: COMPLETE / VERIFIED
- Stage D — Intelligence Adapters: COMPLETE / VERIFIED
- Stage E — Product: COMPLETE / VERIFIED
- Stage F — Release: COMPLETE / SEALED

Sealed commit:

```text
50b27c252de6d5a38eb6958b7e31ba7fe66f5545
```

Final sealed verification: GitHub Actions Run `33540736899` (`NEXUS Verification #236`) — PASS.

The historical `v1.0.0` tag is a fixed verification boundary. Development after that tag does not retroactively change the release claims or evidence.

## Architecture

```text
Human
  |
  v
Browser / Authenticated HTTP Product
  |
  v
Epistemic Workspace
  |-- Question / Goal
  |-- Claims + Provenance + Uncertainty
  |-- Alternatives + Consequences
  |-- Machine Analysis (non-authoritative)
  |-- Explicit Human Judgment
  |-- Append-only Audit History
  |
  v
Constitutional Core
  |-- Authority boundary
  |-- Policy decision
  |-- Authorized request
  |-- Executor
  |
  v
Verification / Evidence / Attestation
```

The gateway may parse, validate shape, create envelopes, delegate, and serialize responses. It does not independently authorize, deny, interpret evidence meaning, execute constitutional actions, or mutate policy.

## Run the gateway locally

The executable product requires a bearer token and fails closed when the token is absent.

```sh
export NEXUS_API_TOKEN='replace-with-a-long-random-secret'
export NEXUS_DATA_DIR='./nexus-data'
export NEXUS_BIND_ADDR='127.0.0.1:3000'

cargo run --manifest-path artifact-05/Cargo.toml --locked
```

Then open:

```text
http://127.0.0.1:3000/
```

Workspace API calls require:

```text
Authorization: Bearer <NEXUS_API_TOKEN>
```

## Container deployment

A pinned Dockerfile is included for post-v1 productionization.

```sh
docker build -t nexus:post-v1 .
mkdir -p nexus-data

docker run --rm \
  -p 3000:3000 \
  -e NEXUS_API_TOKEN='replace-with-a-long-random-secret' \
  -v "$PWD/nexus-data:/data" \
  nexus:post-v1
```

For a real hosted deployment, persistent storage at `/data`, HTTPS termination, and secret injection are required. See `docs/DEPLOYMENT.md`.

## Verification

The verification workflow uses a digest-pinned Rust image and preserves the rule:

> **No real verification -> no claim of PASS -> no seal.**

The pipeline verifies the constitutional core, self-audits its manifest, bundles evidence, creates build provenance attestations, and runs Artifact 05 Gates 0–3 with locked dependencies.

## Repository map

```text
src/                         Constitutional core + epistemic engine + adapters
artifact-05/                 HTTP gateway and product contract tests
web/                         Browser workspace client
docs/PRODUCTION-ROADMAP.md   Completed v1 roadmap
docs/DEPLOYMENT.md           Post-v1 deployment contract
.github/workflows/verify.yml Verification, evidence, and attestation
```

## Release

NEXUS v1.0.0 — Constitutional Infrastructure:

https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.0.0
