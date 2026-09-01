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

### F. Release — READY TO SEAL
- CI verification
- manifest self-audit
- evidence bundle
- artifact attestation
- release seal only after real PASS

## Current status

Stages A through E are implemented and verified under the pinned Docker verification environment. The latest product verification passed the constitutional core, self-audit, Artifact 05 Gates 0–3, test suite, evidence bundling, and attestations. Machine analysis remains non-authoritative, human judgment remains an explicit human transition, and workspace persistence rejects invalid or rewritten histories.

## Current priority

Stage F is the only remaining stage: bind the verified revision and its CI evidence into the release seal, then verify the seal commit itself. No release is considered sealed before that final real PASS.
