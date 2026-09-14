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

## Current status

NEXUS v1.1.0 is the current sealed operational boundary. The v1.0 constitutional/product baseline remains historically fixed; v1.1 adds real durable-host persistence/recovery evidence rather than rewriting the earlier seal.

The v1.1 Stage D evidence was produced on a real external host and bound to the exact deployed commit. The evidence sequence includes HTTPS/auth preflight, capture, provider/service replacement, post-replacement survival, destructive absence observation, and restore verification. The release-readiness gate passed only after the complete lifecycle-bound evidence pack was present and internally consistent.

The referenced exact deployed commit also has a successful NEXUS Verification run that was independently checked before the human release decision and publication of `v1.1.0`.

The seal does not create epistemic authority: machine analysis remains non-authoritative, human judgment remains an explicit human transition, and execution remains behind constitutional authorization.

## Completion rule

No real verification -> no PASS -> no seal.

A release tag is an immutable historical boundary. Later documentation or code changes do not retroactively alter the evidence or claims attached to `v1.0.0` or `v1.1.0`. Any future release must establish its own exact-commit verification and evidence appropriate to its new claims.
