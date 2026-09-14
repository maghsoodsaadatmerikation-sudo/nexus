# NEXUS

**Constitutional infrastructure for human judgment.**

NEXUS is a Rust-based constitutional core, epistemic workspace, authenticated HTTP gateway, browser client, and verification pipeline designed to help humans examine questions, evidence, alternatives, uncertainty, and consequences without transferring meaning, identity, or final decision authority to a machine.

## Core principle

> **NEXUS may assist judgment; NEXUS must not own judgment.**

The system separates human authority, evidence, machine analysis, execution authority, and auditability. The constitutional invariant remains:

```text
A_out <= A_in
```

## Current sealed release — v1.7.0

`v1.7.0` is the current sealed **runtime-provenance and source-tree identity** boundary.

It preserves the earlier durable-host, operational-resilience, production-hardening, deployment-truth, promotion-safety, and exact-promotion boundaries while adding independently reconciled runtime provenance.

### v1.7 release boundary

- Exact release candidate: `9847b293f3b37a574568ba4e450797b312a44984`
- NEXUS Verification run `34887158522`: SUCCESS
- v1.7 Release Gate run `34887347369`: SUCCESS
- Runtime target: `3c0977f4c7fc9fb5e9a78bdb1eeb581cb3cb4959`
- Railway production deployment: `b0e78cf8-af51-4092-9bf6-99e1ac5cc13b` — SUCCESS
- Durable mount: `/data`
- Canonical source-tree SHA-256: `d66021fc1e8c276df2c673d26b05f2de58ef4c81589261cb41aefa1ad047f1c7`
- Independent runtime-identity run `34884505985`: SUCCESS
- Production reconciliation run `34886934100`: SUCCESS
- Public runtime identity: HTTP `200`, schema `nexus.runtime-identity.v1`
- Authority marker: `non_authoritative_build_metadata`
- Observed production digest: exact match
- No paid upgrade, new production service, new production volume, secret disclosure, or authority expansion was required or authorized.

The runtime identity endpoint reports provenance evidence only. It cannot authorize requests, create HumanJudgment, mutate policy, widen execution authority, or substitute for a release decision.

The v1.7 seal is an **operational runtime-provenance boundary**. It does not claim bit-for-bit reproducible binaries across arbitrary builders, formal verification of Railway, universal security, universal availability, or formal proof of epistemic correctness.

Historical `v1.0.0` through `v1.6.0` tags remain immutable earlier boundaries.

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

```sh
export NEXUS_API_TOKEN='replace-with-a-long-random-secret'
export NEXUS_DATA_DIR='./nexus-data'
export NEXUS_BIND_ADDR='127.0.0.1:3000'

cargo run --manifest-path artifact-05/Cargo.toml --locked
```

## Verification

The verification workflow preserves the rule:

> **No real verification -> no claim of PASS -> no seal.**

Continuous verification runs on source changes and at 00:00, 08:00, and 16:00 UTC. Scheduled verification may observe, verify, attest, and report; it carries neither release authority nor production-promotion authority.

## Repository map

```text
src/                                      Constitutional core + epistemic engine + adapters
artifact-05/                              HTTP gateway and product contract tests
web/                                      Browser workspace client
docs/DEPLOYMENT.md                        Deployment contract
docs/RELEASE-v1.1.0.md                    Sealed durable-host release record
docs/RELEASE-v1.2.0.md                    Sealed operational-resilience record
docs/RELEASE-v1.3.0.md                    Sealed production-hardening record
docs/RELEASE-v1.4.0.md                    Sealed deployment-truth record
docs/RELEASE-v1.5.0.md                    Sealed promotion-safety record
docs/RELEASE-v1.6.0.md                    Sealed exact-promotion record
docs/V1.7-ROADMAP.md                      Runtime-provenance roadmap and completed gates
docs/RELEASE-v1.7.0.md                    v1.7 release record
evidence/v1.7/production-runtime-evidence.json
                                           Production runtime-provenance evidence
.github/workflows/v1.7-runtime-identity.yml Independent runtime identity reconciliation
.github/workflows/v1.7-production-reconcile.yml
                                           Public production runtime reconciliation
.github/workflows/release-v1.7.yml          Fail-closed v1.7 release gate
.github/workflows/verify.yml                Verification, evidence, and attestation
```

## Releases

- NEXUS v1.7.0 — Runtime Provenance Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.7.0
- NEXUS v1.6.0 — Exact Promotion Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.6.0
- NEXUS v1.5.0 — Promotion Safety Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.5.0
- NEXUS v1.4.0 — Deployment Truth Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.4.0
- NEXUS v1.3.0 — Production Hardening Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.3.0
- NEXUS v1.2.0 — Operational Resilience Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.2.0
- NEXUS v1.1.0 — Durable Host Verification Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.1.0
- NEXUS v1.0.0 — Constitutional Infrastructure: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.0.0
