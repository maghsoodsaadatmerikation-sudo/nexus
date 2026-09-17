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

### F. v1.0 constitutional release — COMPLETE / SEALED
- constitutional/product CI verification: PASS
- manifest self-audit: PASS
- evidence bundles and attestations: GENERATED
- v1.0 release seal: CREATED

### G. v1.1 durable-host validation — COMPLETE / VERIFIED
- real public HTTPS host: VERIFIED
- private bearer token boundary: VERIFIED
- persistent storage mounted for `NEXUS_DATA_DIR`: VERIFIED
- exact deployed commit capture: VERIFIED
- real service/container replacement event: RECORDED
- post-replacement workspace survival: PASS
- destructive backing-state removal and observed authenticated 404 absence: PASS
- independent snapshot restore and JSON-equivalent verification: PASS
- v1.1 release-readiness gate: PASS
- exact-commit GitHub verification independently checked: SUCCESS

### H. v1.1 release — COMPLETE / SEALED
- tag: `v1.1.0`
- sealed deployed commit: `480f8771c47e41d4d19b22ed4360bd32c4d2f70a`
- NEXUS Verification run: `34824938788` — SUCCESS
- workspace snapshot SHA-256: `71271177cadc1dd67afdf0ddbc913c89c54b326df66bdb2f1dd803da94107d7b`
- human release decision: APPROVED
- GitHub Release: PUBLISHED

### I. v1.2 operational resilience — COMPLETE / SEALED
- operational-resilience evidence established without widening constitutional authority
- exact candidate independently verified before release
- historical v1.1 boundary preserved

### J. v1.3 production hardening — COMPLETE / SEALED
- authority-preserving production hardening gates: PASS
- secret/evidence hygiene and failure transparency: PASS
- exact-candidate release gate: PASS
- historical seals preserved

### K. v1.4 deployment truth — COMPLETE / SEALED
- release identity and observed provider deployment identity recorded separately
- live deployment state reconciled without claiming an unperformed promotion
- durable `/data` continuity preserved

### L. v1.5 promotion safety — COMPLETE / SEALED
- exact immutable promotion target required
- rollback anchor recorded
- moving branch approximation rejected fail-closed
- no paid upgrade or destructive data mutation authorized

### M. v1.6 exact promotion — COMPLETE / SEALED
- exact provider-side source binding established
- provider-side deployment completed successfully
- durable `/data` state preserved
- promotion evidence remained separate from release authorization

### N. v1.7 runtime provenance — COMPLETE / SEALED
- exact runtime target: `3c0977f4c7fc9fb5e9a78bdb1eeb581cb3cb4959`
- Railway production source pin: exact immutable target
- Railway deployment `b0e78cf8-af51-4092-9bf6-99e1ac5cc13b`: SUCCESS
- durable mount `/data`: PRESERVED
- canonical source-tree SHA-256: `d66021fc1e8c276df2c673d26b05f2de58ef4c81589261cb41aefa1ad047f1c7`
- independent runtime-identity reconciliation: PASS
- public production runtime reconciliation: PASS
- runtime authority marker: `non_authoritative_build_metadata`
- exact release candidate: `9847b293f3b37a574568ba4e450797b312a44984`
- exact-candidate NEXUS Verification run `34887158522`: SUCCESS
- v1.7 release gate run `34887347369`: SUCCESS
- tag/release `v1.7.0`: PUBLISHED
- no paid upgrade, new production service, new production volume, secret disclosure, or authority expansion authorized

### O. v1.8 observation boundary — HISTORICAL / SEALED
- later historical release boundary preserved; see its immutable release evidence
- no later capability work rewrites its claims

### P. v1.9 continuous runtime conformance — COMPLETE / SEALED
- repeated read-only runtime observations bound to exact source evidence
- release `v1.9.0` published against exact candidate `87ab795f16bbe68d8c014c5cf31ea66629e27998`
- observation evidence remained non-authoritative
- no production mutation or authority expansion

### Q. v2.0 capability delegation — IMPLEMENTED / VERIFIED ENGINEERING MILESTONE / UNSEALED
- bounded capability grant model introduced
- `A_child <= A_parent <= A_in`
- scope, subject, time, provenance, and revocation checks implemented
- historical v2.0 release gate did not establish a valid seal; later releases do not retroactively repair that boundary

### R. v2.1 capability enforcement boundary — COMPLETE / SEALED
- capability validation moved before `AuthorizedRequest` construction
- invalid validity intervals fail closed
- append-only capability audit observations remain non-authoritative
- exact release candidate: `4bed8ea9ec70bfeb0424c917edb71efb3fd6a3a8`
- v2.1 enforcement verification run `35263378016`: SUCCESS
- canonical NEXUS Verification run `35263377971`: SUCCESS
- release `v2.1.0`: PUBLISHED
- no cryptographic grant authenticity, durable/distributed revocation, federation, provider correctness, or universal-security claim

### S. v2.2 revocation replay integrity — IN ENGINEERING
- ordered provenance-bearing revocation events
- fail-closed replay validation
- effective revoked state reconstructed from event history rather than trusted as an independent snapshot field
- no durable-storage or cryptographic-authenticity claim
- not sealed until exact-candidate verification and v2.2 evidence pass

## Current status

NEXUS `v2.1.0` is the current sealed capability-enforcement boundary. v2.0 remains an unsealed engineering milestone; v2.1 does not retroactively seal it.

v2.2 revocation replay integrity is under engineering and carries no PASS or seal until its own exact-candidate verification and evidence contract succeed.

Historical release tags remain immutable boundaries. Runtime evidence, capability evidence, and release authority remain separate.

## Completion rule

No real verification -> no PASS -> no seal.

A release tag is an immutable historical boundary. Later documentation or code changes do not retroactively alter the evidence or claims attached to earlier releases. Any future release must establish its own exact-commit verification and evidence appropriate to its new claims.
