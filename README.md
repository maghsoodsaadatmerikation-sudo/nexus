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

## Current sealed release — v1.2.0

`v1.2.0` is the current sealed operational-resilience boundary. It preserves the durable-host evidence sealed in v1.1.0 and adds fail-closed controls for historical release integrity, continuous verification, durable-state resilience, operational economy, and release-candidate readiness.

- G1 Release-boundary integrity: PASS
- G2 Continuous verification: PASS
- G3 Durable-state resilience: PASS
- G4 Operational economy: PASS
- G5 Release-candidate gate: PASS
- Exact-candidate GitHub verification: SUCCESS
- Human release decision: APPROVED
- Release: SEALED

Sealed candidate commit:

```text
fbe17b80206df5e63f7351cc97f1794eb8c88e17
```

Independent verification: GitHub Actions Run `34848797043` — SUCCESS.

Evidence artifact digests:

```text
verification-bundle: sha256:3bf37901f06074c6b42cbe322427c21e1f6be8da10cfd01a55e160d3993370ba
artifact-05-verification-bundle: sha256:1e6ee2695c8c40a015b15de00c8a8310a75ddc57922eab6d813179e6cc0547ac
render-stage-d-configuration: sha256:e3f280cc6d2e3d30826cc96f1f57f048064ae910b480f041e46321dab878c932
```

Continuous verification runs on source changes and at 00:00, 08:00, and 16:00 UTC. Scheduled verification may verify and attest evidence but does not carry release authority.

No paid resource upgrade was requested or performed for v1.2. The primary durable service and `/data` volume were preserved. Auxiliary evidence helpers are configured with restart policy `NEVER` and sleeping enabled; because the available Railway action rejects literal zero replicas, NEXUS does not claim provider-side zero replicas.

The v1.2 seal is an **operational verification boundary**. It does not claim formal proof of epistemic correctness, universal availability, universal disaster recovery, or provider-wide billing guarantees, and it does not expand machine authority.

Historical `v1.0.0` and `v1.1.0` tags remain immutable earlier boundaries.

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
docker build -t nexus:v1.2 .
mkdir -p nexus-data

docker run --rm \
  -p 3000:3000 \
  -e NEXUS_API_TOKEN='replace-with-a-long-random-secret' \
  -v "$PWD/nexus-data:/data" \
  nexus:v1.2
```

For a hosted deployment, persistent storage at `/data`, HTTPS termination, secret injection, and lifecycle verification are required. See `docs/DEPLOYMENT.md` and the v1.2 operational-resilience contracts.

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
.github/workflows/verify.yml          Verification, evidence, and attestation
```

## Releases

- NEXUS v1.2.0 — Operational Resilience Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.2.0
- NEXUS v1.1.0 — Durable Host Verification Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.1.0
- NEXUS v1.0.0 — Constitutional Infrastructure: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.0.0
