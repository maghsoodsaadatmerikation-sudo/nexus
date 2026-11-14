# Atomic workspace creation under concurrent gateway instances

Date: 2026-11-14
Base: validated runtime readiness integration PR #201 (head `85bdfb8606fd9295d9e046b783243305426ad037`)
Scope: **draft branch, synthetic and Rust CI only; no production authority**

## Reproduced source-level race

`CoreDelegate::create_workspace` and `import_workspace` previously
issued `repository.load(id)` and then `repository.save(snapshot)` as
separate operations under a **process-local** mutex. A second gateway
instance using the same directory can pass the existence test before the
first instance commits. The durable repository serializes the later
`save` calls with an exclusive filesystem lock, but `save` permits a
compatible or identical history extension. An identical initial snapshot
can therefore be acknowledged as newly created by **both** instances,
while only one logical workspace should ever be created.

Even when competing snapshots differ, the losing process can report a
history-divergence validation error (HTTP 422) instead of a create conflict
(HTTP 409). The import route has the same check-then-write problem.

## Repair

- Add `FileWorkspaceRepository::create_new(snapshot)` for immutable
  create-if-absent behavior, distinct from existing append/update `save`.
- Both methods share a single locked `write_snapshot` implementation.
  `create_new` checks for existence **inside the same cross-process
  exclusive directory lock** as the durable temp-file fsync + rename and
  directory fsync. Existing IDs always produce explicit
  `DurableWorkspaceError::AlreadyExists`, even if payloads match.
- Real gateway create/import now use `create_new` and map the result to
  HTTP 409 `workspace_already_exists`; no unlocked existence test remains.
- Preserve `save` history-extension rules for legitimate workspace updates,
  including detection of rollback or divergent audit trails.

## Tests

A Rust filesystem regression launches eight independent pinned repository
instances behind a barrier, all attempting the **same identical initial
workspace**. Exactly one succeeds, seven obtain AlreadyExists, stored
content is unchanged, and a legitimate history extension remains possible.

A gateway HTTP regression creates two **separate CoreDelegate** instances
over the same synthetic root and requires one 201 / one 409 for create,
then confirms import of the same snapshot is 201 followed by 409.
Exact-head CI additionally runs the existing durable resilience/recovery,
ENOSPC and public exposure checks.

## Limits / self-critique

Cross-process locking assumes cooperating writers on the same local
filesystem and its expected `flock` semantics. This is not a distributed
database consensus protocol; a filesystem without reliable advisory
locks, split-brain mounts or writes outside the repository may still
violate the guarantee. Hardening cross-host distributed coordination
would need a real transactional service or ownership lease and evidence
on the chosen provider.

The change does not retrofit previously duplicated acknowledgments or
grant automatic data reconciliation. No production data or hosted provider
configuration is changed. Continue holding main merges until the GitHub
ruleset requires current-head checks, Render auto-deploy is under control,
and independent full-data restore has real offsite proof.
