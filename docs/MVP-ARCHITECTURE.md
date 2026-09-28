# NEXUS MVP Architecture

## Product contract

NEXUS is a human-judgment workspace, not an automated decision maker.

The MVP flow is:

`Question → Goal/Constraints/Values → Claims/Evidence → Alternatives → Human Judgment → Export`

Machine-generated analysis may be represented as a claim with `MachineAnalysis` origin, but it cannot populate `HumanJudgment` implicitly.

## Current implementation

- `src/epistemic.rs`: constitutional domain model for DecisionWorkspace, Claim, Alternative, Uncertainty and HumanJudgment.
- `web/index.html`: dependency-free browser MVP. It is local-first and can be opened as a static page.
- Export is explicit JSON so the workspace can later be handed to a server/API without changing the domain model.

## Authority boundary

The product must preserve these distinctions:

1. Evidence is not authority.
2. Machine interpretation is not human judgment.
3. Alternatives are not recommendations.
4. A final decision exists only after explicit human entry.
5. The UI must never silently transform an AI output into a human decision.

## Next production layers

1. HTTP Gateway over the existing Constitutional Core.
2. Persistent DecisionWorkspace storage with provenance and append-only audit events.
3. Authentication and per-workspace authorization.
4. Research/evidence adapters with source provenance.
5. AI challenge/analysis adapter that can only emit non-authoritative epistemic objects.
6. Web client connected to the gateway.
7. Verification and attestation for releases.

## Non-goals for the MVP

- Autonomous decisions.
- Silent recommendation ranking presented as authority.
- Autonomous policy mutation.
- Direct AI access to execution capabilities.
