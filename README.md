# NEXUS

**Constitutional infrastructure for human judgment.**

NEXUS is a Rust-based constitutional core, epistemic workspace, authenticated HTTP gateway, browser client, and verification pipeline designed to help humans examine questions, evidence, alternatives, uncertainty, and consequences without transferring meaning, identity, or final decision authority to a machine.

## Core principle

> **NEXUS may assist judgment; NEXUS must not own judgment.**

The system separates human authority, evidence, machine analysis, execution authority, and auditability. The constitutional invariant remains:

```text
A_out <= A_in
```

## Current sealed release — v1.5.0

`v1.5.0` is the current sealed **promotion-safety and rollback-readiness** boundary.

It preserves the earlier durable-host, operational-resilience, production-hardening, and deployment-truth seals while enforcing one additional distinction:

**verified release != authorized promotion != executed promotion != observed production state**

### v1.5 release boundary

- G1 Historical release integrity: PASS
- G2 Promotion target identity: PASS
- G3 Pre-cutover durable-state safety: PASS
- G4 Exact-SHA execution requirement: PASS
- G5 Post-cutover evidence requirement: PASS
- G6 Rollback readiness: PASS
- G7 Operational economy: PASS
- G8 Exact-candidate release gate: PASS
- Exact-candidate GitHub verification: SUCCESS
- Release: SEALED

Sealed candidate commit:

```text
84d1c283494e1203e63d6a892351938dfc24a5ed
```

NEXUS Verification: GitHub Actions Run `34879097015` — SUCCESS.

Promotion target defined by v1.5:

```text
v1.4.0 @ dcf49302e8a8c4c935de3aad0585b19132bad2cd
```

Observed pre-cutover production truth:

```text
provider: Railway
service: nexus-stage-d
status: SUCCESS
live commit: 480f8771c47e41d4d19b22ed4360bd32c4d2f70a
deployment: 1f63e3b9-768f-441e-a524-b061394b922e
durable mount: /data
```

Production promotion was **not performed**. The connected provider tooling did not expose a verified exact-commit source pin for the existing primary service, so NEXUS failed closed rather than approximating the promotion through a moving `main` branch.

This is intentional. A future cutover requires an immutable target binding and new provider-side post-cutover evidence proving deployment `SUCCESS`, the exact promoted identity, durable `/data`, and no authority expansion.

No paid resource upgrade, new service, or new volume was required for v1.5.

The v1.5 seal is an **operational promotion-safety boundary**. It does not claim formal proof of epistemic correctness, universal security, universal availability, or that v1.5.0/v1.4.0 is currently deployed in production.

Historical `v1.0.0` through `v1.4.0` tags remain immutable earlier boundaries.

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
src/                                  Constitutional core + epistemic engine + adapters
artifact-05/                          HTTP gateway and product contract tests
web/                                  Browser workspace client
docs/DEPLOYMENT.md                    Deployment contract
docs/RELEASE-v1.1.0.md                Sealed durable-host release record
docs/RELEASE-v1.2.0.md                Sealed operational-resilience record
docs/RELEASE-v1.3.0.md                Sealed production-hardening record
docs/RELEASE-v1.4.0.md                Sealed deployment-truth record
docs/V1.5-ROADMAP.md                  v1.5 promotion-safety roadmap
docs/V1.5-RELEASE-GATE.md             v1.5 promotion/release gate
docs/RELEASE-v1.5.0.md                Sealed v1.5 release record
evidence/live-deployment-state.json   Provider-observed deployment attestation
.github/workflows/verify.yml          Verification, evidence, and attestation
```

## Releases

- NEXUS v1.5.0 — Promotion Safety Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.5.0
- NEXUS v1.4.0 — Deployment Truth Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.4.0
- NEXUS v1.3.0 — Production Hardening Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.3.0
- NEXUS v1.2.0 — Operational Resilience Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.2.0
- NEXUS v1.1.0 — Durable Host Verification Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.1.0
- NEXUS v1.0.0 — Constitutional Infrastructure: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.0.0
