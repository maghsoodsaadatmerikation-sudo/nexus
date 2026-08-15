# NEXUS

**Constitutional infrastructure for human judgment.**

NEXUS is a Rust-based constitutional core and epistemic workspace designed to help humans examine questions, evidence, alternatives, uncertainty, and consequences without transferring meaning, identity, or final decision authority to a machine.

## Core principle

> **NEXUS may assist judgment; NEXUS must not own judgment.**

The system therefore separates:

- **Human authority** — values, identity, and final judgment remain human-owned.
- **Evidence** — claims retain explicit provenance and uncertainty.
- **Machine analysis** — analysis may be recorded, challenged, and compared, but is not silently promoted to human judgment.
- **Execution authority** — execution remains behind the constitutional authorization boundary.
- **Auditability** — important state transitions are intended to be reproducible and inspectable.

## Current architecture

```text
Human
  |
  v
Epistemic Workspace
  |-- Question / Goal
  |-- Constraints / Values
  |-- Claims + Provenance + Uncertainty
  |-- Alternatives + Consequences
  |-- Human Judgment
  |
  v
Constitutional Core
  |-- Authority boundary
  |-- Policy decision
  |-- Authorized request
  |-- Executor
  |-- Audit
  |
  v
Verification / Evidence / Attestation
```

The `epistemic` module is deliberately a **recording and structuring layer**. It does not contain an AI recommender and it does not create a human judgment from machine output.

## Development status

- Constitutional Rust core: implemented.
- Authority/execution boundary: implemented.
- Epistemic workspace primitives: implemented.
- Verification protocol and Artifact 05: under active hardening; completion is not claimed until a real CI verification produces auditable evidence.
- End-user web product: next implementation layer.

## Non-negotiable invariant

**No real verification -> no claim of PASS -> no seal.**

See the repository workflows and `artifact-05/` for the verification protocol.
