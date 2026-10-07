# NEXUS

**Constitutional infrastructure for human judgment.**

NEXUS is a Rust-based constitutional core, epistemic workspace, authenticated HTTP gateway, browser client, and verification pipeline designed to help humans examine questions, evidence, alternatives, uncertainty, and consequences without transferring meaning, identity, or final decision authority to a machine.

## Core principle

> **NEXUS may assist judgment; NEXUS must not own judgment.**

The system separates human authority, evidence, machine analysis, execution authority, and auditability. The constitutional invariant remains:

```text
A_out <= A_in
```

## Current sealed release — v2.5.0

`v2.5.0` is the current sealed **unified transport-authentication** boundary.

It preserves the earlier constitutional, runtime, capability-enforcement, revocation, and gateway authority-confusion boundaries while requiring configured bearer authentication before request parsing, constitutional delegation, or request-status lookup.

### v2.5 release boundary

- Exact release candidate: `200ff827efed0a165548e9dbc2b6801d23d6ddfb`
- Invariant: `A_out <= A_in`
- NEXUS v2.5 Unified Transport Authentication Verification run `36385219907`: SUCCESS
- Canonical NEXUS Verification run `36385219924`: SUCCESS
- Release Gate run `36385267448`: SUCCESS
- Exact-candidate evidence attestation: VERIFIED
- Missing and incorrect credentials: REJECTED FAIL-CLOSED
- Authenticated `POST /v1/requests`: asynchronous `202 Accepted`
- Authenticated `GET /v1/requests/{id}`: status/`404` semantics preserved
- Release evidence SHA-256: `c64546d8b96e99338ba9cc41a93e0f825b151e8627b436d321ade31b5a432c46`
- Production mutation: NONE
- Authority expansion: NONE

The v2.5 seal is a **transport-authentication boundary**. It does not claim credential rotation, external identity federation, rate limiting, distributed session state, durable persistence, consensus, universal security, or external-system linearizability. Authentication permits access to a transport boundary; it does not create constitutional authority.

Historical release tags remain immutable earlier boundaries. In particular, v2.0 remains an unsealed engineering milestone; later releases do not retroactively seal it.

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
artifact-06/                              Synthetic Reality Lab contract and CT-001..020 map
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
docs/V2.2-REVOCATION-REPLAY.md             Revocation replay integrity contract
docs/RELEASE-v2.2.0.md                    v2.2 sealed release record
docs/V2.3-REVOCATION-FRESHNESS.md           Stale-authority defense contract
docs/RELEASE-v2.3.0.md                    v2.3 sealed release record
evidence/v1.7/production-runtime-evidence.json
                                           Production runtime-provenance evidence
.github/workflows/v1.7-runtime-identity.yml Independent runtime identity reconciliation
.github/workflows/v1.7-production-reconcile.yml
                                           Public production runtime reconciliation
.github/workflows/release-v1.7.yml          Fail-closed v1.7 release gate
.github/workflows/verify.yml                Verification, evidence, and attestation
```

## Releases

- NEXUS v2.5.0 — Unified Transport Authentication Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v2.5.0
- NEXUS v2.4.0 — Gateway Authority-Confusion Defense Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v2.4.0
- NEXUS v2.3.0 — Revocation Freshness / Stale-Authority Defense Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v2.3.0
- NEXUS v2.2.0 — Revocation Replay Integrity Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v2.2.0
- NEXUS v2.1.0 — Capability Enforcement Boundary Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v2.1.0
- NEXUS v1.7.0 — Runtime Provenance Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.7.0
- NEXUS v1.6.0 — Exact Promotion Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.6.0
- NEXUS v1.5.0 — Promotion Safety Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.5.0
- NEXUS v1.4.0 — Deployment Truth Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.4.0
- NEXUS v1.3.0 — Production Hardening Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.3.0
- NEXUS v1.2.0 — Operational Resilience Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.2.0
- NEXUS v1.1.0 — Durable Host Verification Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.1.0
- NEXUS v1.0.0 — Constitutional Infrastructure: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.0.0
