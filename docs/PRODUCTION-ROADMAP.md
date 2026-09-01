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

### C. Gateway — IMPLEMENTED / VERIFIED BOUNDARY
- HTTP request envelope
- shape validation only at the gateway
- delegation to the constitutional core
- no policy mutation or autonomous authorization in the gateway
- workspace and analysis ingestion delegate into the core epistemic engine

### D. Intelligence adapters
- research/evidence adapter
- AI challenge adapter
- machine outputs represented only as non-authoritative epistemic objects
- explicit uncertainty and source provenance

### E. Product
- authenticated workspaces
- browser client connected to the gateway
- export/import
- audit history and provenance replay

### F. Release
- CI verification
- manifest self-audit
- evidence bundle
- artifact attestation
- release seal only after real PASS

## Current status

Stage B, the Epistemic Engine, is complete and verified. Its completed boundary includes durable JSON-backed workspace persistence, atomic file replacement, append-only history protection, provenance-carrying audit events, explicit human-judgment transitions, and schema-version validation. The completed Stage B invariants preserve the constitutional rule that machine analysis cannot implicitly become human judgment.

## Current priority

The next unsealed priority is Stage D intelligence-adapter hardening and integration. Research/evidence and AI challenge outputs must continue to enter the system only as non-authoritative epistemic objects with explicit provenance and uncertainty; they must not bypass the completed Stage B or constitutional authorization boundaries.
