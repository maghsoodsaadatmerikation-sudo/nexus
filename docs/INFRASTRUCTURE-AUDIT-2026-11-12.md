# Infrastructure audit: workspace persistence and reproducible verification

Scope: inspected `main` at `1b9f1dbc4544cfc608229cb7a8464e60f08aaf40`.
This is an engineering repair, not a new release seal or production-readiness claim.

## Reproduced defects and repairs

| Defect | Consequence | Repair |
| --- | --- | --- |
| Snapshot file is synced but its rename/parent directories are not | A successful save does not establish filesystem crash durability | Sync created directory ancestry before writing, then sync the containing directory after rename; propagate failures |
| Fixed `*.json.tmp` opened with truncation | Interrupted writes or another writer's temporary file can be overwritten; a pre-existing symlink can redirect truncation | Exclusively create a distinct temporary file, retry occupied names, clean up only the created temporary path |
| Snapshot permissions inherit the process umask | A typical umask can make private workspace content readable by other local users | Create snapshot temporary files with Unix mode `0600`; atomic rename retains that mode |
| Loaded JSON is not bound to the requested workspace ID | A valid snapshot copied under another filename can be returned as the wrong workspace | Reject a mismatch with `WorkspaceIdentityMismatch` |
| History validation compares events containing IDs but not previous payloads | Existing question, claims, alternatives or initial metadata can be silently rewritten while preserving events | Require immutable initial metadata and exact existing claim/alternative content prefixes; append operations and explicit judgment transitions remain supported |
| Pinned Rust 1.85 formatting and compile-failure diagnostic fixture are stale | Local documented verification fails before completing | Apply the pinned formatter and refresh the E0603 fixture; the attempted authority forgery must still fail compilation |
| Recovery CI assumes candidate workspace source always equals old deployed source | Any persistence repair makes the audit job fail before testing | Check an independently checked-out historical reference against the unchanged blob pins; test candidate persistence separately |

Four regression tests were executed against a scratch copy of the original persistence
implementation: all four failed, with five pre-existing persistence tests passing.
The same four tests pass with the repair. The content-rewrite test covers seven
different mutations and verifies that rejected saves preserve the prior snapshot.

## Validation

- Rust 1.85.0, locked dependencies: complete core suite, 97 tests passed,
  including CT-001 through CT-020 and compile-failure authority boundary.
- Gateway suite: 54 tests passed; the existing filesystem-capacity exhaustion
  test remains ignored in an ordinary unprivileged run.
- `scripts/run_gates.sh`: formatting, locked build/check/test compilation,
  complete tests, type boundary and lockfile metadata.
- Snapshot/recovery and durable-state Python contracts run separately.

These are local synthetic checks. They do not simulate physical power loss,
certify a filesystem/provider's fsync implementation, or prove production recovery.
If final directory sync fails after rename, the API returns an error although the
new snapshot may already be visible. Re-read and reconcile before retrying.

## Provider observations and outstanding work

Read-only Railway observations on 2026-11-12:

- Project `NEXUS Stage D`, production environment: no staged changes.
- Primary service `nexus-stage-d`: deployment state `SLEEPING`; source configuration
  pins `3c0977f4c7fc9fb5e9a78bdb1eeb581cb3cb4959`, not current `main`.
- `nexus-data-lMm1` remains attached at `/data`; provider inventory reports 1 MB.
  That inventory value is not a measurement of free filesystem space.
- Restore service is also `SLEEPING`; historical `stage-d-runner` is `FAILED`.
- No fresh independent production-volume backup/restore was established by these
  observations. No service, volume, source pin, billing plan or release gate changed.

Production promotion remains blocked on a fresh independently recoverable backup,
verified source/runtime identity and host acceptance. Existing static/offline pilot
deployment is separate from the Rust gateway and is not upgraded by this patch.

The file repository still requires a trusted directory and one coordinated writer
(the gateway's mutex provides coordination within one process). Unique temporary
files do not provide cross-process history transactions, protection from hostile
directory/ancestor replacement, encryption at rest, quotas or a continuous backup.
Those boundaries must not be described as solved by this change.

Recovery CI now compiles the current audit harness with the historical workspace
modules and current locked dependencies for synthetic intake tests. This is not
a recreation or attestation of the historical executable. The production intake
parity guard is unchanged and still blocks the changed candidate sources when
they are presented as the old deployed revision.
