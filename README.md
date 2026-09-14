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

## Current sealed release — v1.4.0

`v1.4.0` is the current sealed **deployment-truth and evidence-reconciliation** boundary. It preserves the earlier durable-host, operational-resilience, and production-hardening seals while making three claims explicitly non-interchangeable:

- **Released** — a verified Git tag/GitHub Release exists.
- **Verified** — the exact candidate passed the stated verification workflow and gates.
- **Observed live** — provider-side evidence identifies a production deployment commit.

### v1.4 release boundary

- G1 Historical seal integrity: PASS
- G2 Live deployment attestation: PASS
- G3 Release/deployment reconciliation: PASS
- G4 Claim discipline: PASS
- G5 Durable-boundary continuity: PASS
- G6 Operational economy: PASS
- G7 Exact-candidate release gate: PASS
- Exact-candidate GitHub verification: SUCCESS
- Release workflow: SUCCESS
- Human release authorization: APPROVED
- Release: SEALED

Sealed candidate commit:

```text
dcf49302e8a8c4c935de3aad0585b19132bad2cd
```

Independent verification: GitHub Actions Run `34877496665` — SUCCESS.

Release workflow: GitHub Actions Run `34877753394` — SUCCESS.

### Production truth at v1.4 candidate time

Provider-side observation recorded the Railway primary service `nexus-stage-d` as:

```text
deployment status: SUCCESS
observed live commit: 480f8771c47e41d4d19b22ed4360bd32c4d2f70a
durable data mount: /data
relation to latest sealed predecessor: LIVE_BEHIND_RELEASE
```

This is intentional evidence, not an error to hide. **Publishing v1.4.0 did not promote production to v1.4.0.** A production-promotion claim requires new provider-side evidence.

Continuous verification runs on source changes and at 00:00, 08:00, and 16:00 UTC. Scheduled verification may observe, verify, attest, and report, but it does not carry release authority or production-repair authority.

No paid resource upgrade was authorized or required for v1.4. The durable `/data` boundary remains the observed production persistence boundary. Auxiliary evidence helpers remain outside the production authority path.

The v1.4 seal is an **operational release-truth boundary**. It does not claim formal proof of epistemic correctness, universal security, universal availability, universal disaster recovery, provider-wide billing guarantees, or that v1.4.0 is currently deployed in production.

Historical `v1.0.0`, `v1.1.0`, `v1.2.0`, and `v1.3.0` tags remain immutable earlier boundaries.

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
docker build -t nexus:v1.4 .
mkdir -p nexus-data

docker run --rm \
  -p 3000:3000 \
  -e NEXUS_API_TOKEN='replace-with-a-long-random-secret' \
  -v "$PWD/nexus-data:/data" \
  nexus:v1.4
```

For a hosted deployment, persistent storage at `/data`, HTTPS termination, secret injection, lifecycle verification, and provider-side deployment attestation are required. See `docs/DEPLOYMENT.md`, `docs/V1.4-ROADMAP.md`, and `docs/V1.4-RELEASE-GATE.md`.

## Verification

The verification workflow preserves the rule:

> **No real verification -> no claim of PASS -> no seal.**

The pipeline verifies the constitutional core, self-audits its manifest, bundles evidence, creates build provenance attestations, runs Artifact 05 gates with locked dependencies, tests release and operational gates fail-closed, and verifies deployment-truth reconciliation without mutating production.

## Repository map

```text
src/                                  Constitutional core + epistemic engine + adapters
artifact-05/                          HTTP gateway and product contract tests
web/                                  Browser workspace client
docs/DEPLOYMENT.md                    Deployment contract
docs/RELEASE-v1.1.0.md                Sealed durable-host release record
docs/V1.2-ROADMAP.md                  v1.2 operational-resilience roadmap
docs/RELEASE-v1.2.0.md                Sealed v1.2 release record
docs/V1.3-ROADMAP.md                  v1.3 production-hardening roadmap
docs/RELEASE-v1.3.0.md                Sealed v1.3 release record
docs/V1.4-ROADMAP.md                  v1.4 deployment-truth roadmap
docs/V1.4-RELEASE-GATE.md             v1.4 release/deployment claim gate
docs/RELEASE-v1.4.0.md                Sealed v1.4 release record
evidence/live-deployment-state.json   Provider-observed deployment attestation
.github/workflows/verify.yml          Verification, evidence, and attestation
```

## Releases

- NEXUS v1.4.0 — Deployment Truth Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.4.0
- NEXUS v1.3.0 — Production Hardening Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.3.0
- NEXUS v1.2.0 — Operational Resilience Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.2.0
- NEXUS v1.1.0 — Durable Host Verification Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.1.0
- NEXUS v1.0.0 — Constitutional Infrastructure: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.0.0
