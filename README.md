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

## Current sealed release — v1.3.0

`v1.3.0` is the current sealed authority-preserving production-hardening boundary. It preserves the earlier durable-host and operational-resilience seals and adds fail-closed controls for historical seal integrity, gateway authority non-expansion, secret/evidence hygiene, provenance/dependency integrity, failure transparency, operational economy, and exact-candidate release readiness.

- G1 Historical seal integrity: PASS
- G2 Gateway authority non-expansion: PASS
- G3 Secret and evidence hygiene: PASS
- G4 Provenance and dependency integrity: PASS
- G5 Failure transparency: PASS
- G6 Operational economy: PASS
- G7 Exact-candidate release gate: PASS
- Exact-candidate GitHub verification: SUCCESS
- Independent verification before publication: SUCCESS
- Human release decision: APPROVED
- Release: SEALED

Sealed candidate commit:

```text
458260fcadc95b53d5e33fa2fabf806519a8cccd
```

Independent verification: GitHub Actions Run `34873937406` — SUCCESS.

Release workflow: GitHub Actions Run `34874211266` — SUCCESS.

Evidence artifact digests:

```text
verification-bundle: sha256:d324c4c7ca0754e45c639b41cd3870e07c7b41712d1f7a532ffeeeaf47fedfab
artifact-05-verification-bundle: sha256:ca4fd0f730c1fe248ad41a38f5d2a6523ead6ef9450611e2f10caac31b7e3e51
render-stage-d-configuration: sha256:e97553dbb15da13d90ddb0723ea6d2418e9edfe7cbb0f3d3fd3701e5ee1b509c
```

Continuous verification runs on source changes and at 00:00, 08:00, and 16:00 UTC. Scheduled verification may observe, verify, attest, and report, but it does not carry release authority or production-repair authority.

No paid resource upgrade was authorized or required for v1.3. The primary durable service and `/data` volume remain the production persistence boundary. Auxiliary evidence helpers remain outside the production authority path. Because the available Railway API does not permit a literal zero-replica value for the configured helpers, NEXUS does not claim provider-side zero replicas or a provider-wide billing guarantee.

The v1.3 seal is an **operational verification boundary**. It does not claim formal proof of epistemic correctness, universal security, universal availability, universal disaster recovery, or provider-wide billing guarantees, and it does not expand machine authority.

Historical `v1.0.0`, `v1.1.0`, and `v1.2.0` tags remain immutable earlier boundaries.

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
docker build -t nexus:v1.3 .
mkdir -p nexus-data

docker run --rm \
  -p 3000:3000 \
  -e NEXUS_API_TOKEN='replace-with-a-long-random-secret' \
  -v "$PWD/nexus-data:/data" \
  nexus:v1.3
```

For a hosted deployment, persistent storage at `/data`, HTTPS termination, secret injection, and lifecycle verification are required. See `docs/DEPLOYMENT.md` and the v1.3 production-hardening contracts.

## Verification

The verification workflow preserves the rule:

> **No real verification -> no claim of PASS -> no seal.**

The pipeline verifies the constitutional core, self-audits its manifest, bundles evidence, creates build provenance attestations, runs Artifact 05 gates with locked dependencies, and tests release and operational gates fail-closed.

## Repository map

```text
src/                                  Constitutional core + epistemic engine + adapters
artifact-05/                          HTTP gateway and product contract tests
web/                                  Browser workspace client
docs/DEPLOYMENT.md                    Deployment contract
docs/RELEASE-v1.1.0.md                Sealed durable-host release record
docs/V1.2-ROADMAP.md                  v1.2 operational-resilience roadmap
docs/V1.2-DURABLE-STATE.md            v1.2 durable-state contract
docs/V1.2-OPERATIONAL-ECONOMY.md      v1.2 cost/resource boundary
docs/V1.2-RELEASE-GATE.md             v1.2 release gate
docs/RELEASE-v1.2.0.md                Sealed v1.2 release record
docs/V1.3-ROADMAP.md                  v1.3 production-hardening roadmap
docs/V1.3-RELEASE-GATE.md             v1.3 release gate
docs/RELEASE-v1.3.0.md                Sealed v1.3 release record
.github/workflows/verify.yml          Verification, evidence, and attestation
```

## Releases

- NEXUS v1.3.0 — Production Hardening Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.3.0
- NEXUS v1.2.0 — Operational Resilience Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.2.0
- NEXUS v1.1.0 — Durable Host Verification Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.1.0
- NEXUS v1.0.0 — Constitutional Infrastructure: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.0.0
