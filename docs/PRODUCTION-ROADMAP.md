# NEXUS Production Roadmap

NEXUS is built as infrastructure for human judgment, not an automated decision-maker.

## Release gates

A production release must preserve four boundaries:

1. Machine analysis never becomes human judgment implicitly.
2. Evidence retains provenance and uncertainty.
3. Execution remains behind constitutional authorization.
4. A release is not sealed without reproducible verification evidence.

## Implementation order

### A. Constitutional foundation
- Rust core and authority boundary
- deterministic verification
- Artifact 05 evidence and attestation

### B. Epistemic engine
- DecisionWorkspace persistence
- append-only audit events
- provenance identifiers
- explicit human judgment transitions
- schema/version compatibility

### C. Gateway
- HTTP request envelope
- shape validation only at the gateway
- delegation to the constitutional core
- no policy mutation or autonomous authorization in the gateway

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

## Current priority

The highest-priority blocker is GitHub Actions job provisioning for Artifact 05. No product layer should bypass that verification boundary. In parallel, product implementation can proceed against the existing domain model without weakening the constitution.
