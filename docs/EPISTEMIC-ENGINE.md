# NEXUS Epistemic Engine — Stage B Contract

## Purpose

The Epistemic Engine persists human decision work without converting machine analysis into authority or human judgment.

## Required invariants

1. `DecisionWorkspace` snapshots carry an explicit schema version.
2. Persistence validates the snapshot before storage and after loading.
3. Durable writes are atomic at the file boundary.
4. Existing audit history cannot be truncated, reordered, or rewritten by a later save.
5. Every claim and alternative in workspace state has a matching append-only audit event in the same order.
6. Every event has an explicit provenance identifier.
7. Human judgment can change only through an explicit `HumanJudgmentTransition` event whose `previous` value matches the audited prior state.
8. Unsupported schema versions fail closed.
9. Machine-origin claims remain claims; they never populate `HumanJudgment` implicitly.

## Persistence model

`InMemoryWorkspaceRepository` supports deterministic tests and ephemeral use. `FileWorkspaceRepository` is the durable reference repository for Stage B. It stores one JSON snapshot per workspace, uses a filesystem-safe encoding of workspace IDs, validates existing history before replacement, writes to a temporary file, syncs it, then atomically renames it into place.

## Boundary

The Epistemic Engine records epistemic state and explicit human transitions. It does not authorize execution, mutate constitutional policy, or grant machine output human authority.
