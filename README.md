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

## Current sealed release — v1.1.0

`v1.1.0` is the current sealed operational release boundary. It extends the v1.0 constitutional/product baseline with real durable-host lifecycle evidence.

- Constitutional/product baseline: COMPLETE / VERIFIED
- HTTPS/auth preflight on external host: PASS
- Persistent workspace capture: PASS
- Real service replacement event: RECORDED
- Post-replacement survival: PASS
- Destructive backing-state absence check: PASS
- Restore verification: PASS
- v1.1 release-readiness gate: PASS
- Exact-commit GitHub verification: SUCCESS
- Human release decision: APPROVED
- Release: SEALED

Sealed deployed commit:

```text
480f8771c47e41d4d19b22ed4360bd32c4d2f70a
```

Independent verification: GitHub Actions Run `34824938788` — SUCCESS.

Workspace snapshot SHA-256:

```text
71271177cadc1dd67afdf0ddbc913c89c54b326df66bdb2f1dd803da94107d7b
```

The v1.1 seal is an **operational verification boundary**. It does not claim formal proof of epistemic correctness and does not expand machine authority.

The historical `v1.0.0` tag remains a fixed earlier boundary and is not rewritten by v1.1.

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

A digest-pinned Dockerfile is included.

```sh
docker build -t nexus:v1.1 .
mkdir -p nexus-data

docker run --rm \
  -p 3000:3000 \
  -e NEXUS_API_TOKEN='replace-with-a-long-random-secret' \
  -v "$PWD/nexus-data:/data" \
  nexus:v1.1
```

For a hosted deployment, persistent storage at `/data`, HTTPS termination, secret injection, and lifecycle verification are required. See `docs/DEPLOYMENT.md`, `docs/STAGE-D-EVIDENCE.md`, and `docs/RELEASE-READINESS-v1.1.md`.

## Verification

The verification workflow preserves the rule:

> **No real verification -> no claim of PASS -> no seal.**

The pipeline verifies the constitutional core, self-audits its manifest, bundles evidence, creates build provenance attestations, runs Artifact 05 gates with locked dependencies, and tests the release-gate logic fail-closed.

## Repository map

```text
src/                              Constitutional core + epistemic engine + adapters
artifact-05/                      HTTP gateway and product contract tests
web/                              Browser workspace client
docs/PRODUCTION-ROADMAP.md        Release history and verified production boundary
docs/DEPLOYMENT.md                Deployment contract
docs/STAGE-D-EVIDENCE.md          Durable-host lifecycle evidence protocol
docs/RELEASE-READINESS-v1.1.md    v1.1 release gate
docs/RELEASE-v1.1.0.md            Sealed v1.1 release record
.github/workflows/verify.yml      Verification, evidence, and attestation
```

## Releases

- NEXUS v1.1.0 — Durable Host Verification Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.1.0
- NEXUS v1.0.0 — Constitutional Infrastructure: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.0.0
