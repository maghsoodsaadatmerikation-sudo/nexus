# NEXUS Production Roadmap

NEXUS is built as infrastructure for human judgment, not an automated decision-maker.

## Release gates

A production release must preserve four boundaries:

1. Machine analysis never becomes human judgment implicitly.
2. Evidence retains provenance and uncertainty.
3. Execution remains behind constitutional authorization.
4. A release is not sealed without reproducible verification evidence.

## Implementation order

### A. Constitutional foundation — COMPLETE / VERIFIED
- Rust core and authority boundary
- deterministic verification
- Artifact 05 evidence and attestation

### B. Epistemic engine — COMPLETE / VERIFIED
- durable DecisionWorkspace persistence
- append-only audit events with rollback/divergence rejection
- explicit provenance identifiers
- explicit human judgment transitions with transition replay validation
- schema/version compatibility with fail-closed unsupported-version handling
- machine analysis retained as non-authoritative epistemic state

### C. Gateway — COMPLETE / VERIFIED
- HTTP request envelope
- shape validation only at the gateway
- delegation to the constitutional core
- no policy mutation or autonomous authorization in the gateway
- workspace and analysis ingestion delegate into the core epistemic engine

### D. Intelligence adapters — COMPLETE / VERIFIED
- pluggable research/evidence provider boundary
- pluggable AI challenge provider boundary
- research observations fail closed without source provenance
- challenge output restricted to counterargument, assumption, and uncertainty observations
- all adapter materialization remains MachineAnalysis origin and cannot create HumanJudgment
- explicit uncertainty and source identifiers preserved

### E. Product — COMPLETE / VERIFIED
- bearer-authenticated workspace API with fail-closed production token requirement
- durable FileWorkspaceRepository used by the executable gateway
- browser client connected to authenticated gateway routes
- validated snapshot import and explicit JSON export
- append-only audit history and provenance replay visible in the browser
- contract tests for missing/wrong/correct authentication and invalid import rejection

### F. Release — COMPLETE / SEALED
- CI verification: PASS
- manifest self-audit: PASS
- evidence bundle: GENERATED
- artifact attestation: GENERATED
- release seal created only after real PASS
- seal record: `release-v1.0-sealed`

## Current status

Stages A through F are complete. NEXUS v1.0 is sealed against the real successful verification of source revision `ee04bb05e8a07e9f5148d8ed85b6caf0aee27ac7`, workflow run `33540467578` (#233). That run passed the constitutional core, self-audit, Artifact 05 Gates 0–3, product contract tests, evidence bundling, and attestations. The release seal records the exact core and Artifact 05 evidence artifact digests.

The seal does not create epistemic authority: machine analysis remains non-authoritative, human judgment remains an explicit human transition, and execution remains behind constitutional authorization.

## Completion rule

No real verification -> no PASS -> no seal. The v1.0 seal was created only after the referenced real SUCCESS run. The seal/documentation head is itself subject to the same verification workflow; a failing head supersedes completion status until repaired.
