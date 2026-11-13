# Storage paths and Studio transition integrity — 13 November 2026

Baseline: `51468481c3a675e125682480826445d350166f71`.
This follow-up reviews file-backed workspace transactions and Studio transitions.
It does not claim a complete security audit or model-capability equivalence.

## Confirmed failures and changes

| Finding | Before | After |
| --- | --- | --- |
| Snapshot aliases | The loader followed final-path symlinks and accepted hard-linked snapshots | Reject symlinks, dangling symlinks, nonregular files and Unix hard links; verify the opened inode against the directory entry |
| Blocking special files | Opening a FIFO as a snapshot could block a caller indefinitely | Check file type before opening, use Unix no-follow/nonblocking flags and check the opened file again |
| Mutable storage path | The lock, history read, temporary file, rename and sync resolved the root pathname independently | Pin one directory per operation; Linux child paths resolve through its descriptor; validate the visible root before/after critical work and sync the pinned directory |
| Inconsistent snapshot read | Size was bounded but identity/content metadata were not compared across reading | Compare inode, length, modification/change times and link count before/after reading and against the final directory entry; reject a changed snapshot |
| Unsent message loss | Unlock checked applied state and editor/profile drafts, but overlooked unsent message text | Require the existing replacement confirmation for an unsent message as well; declining preserves state, draft and passphrase |
| Misleading branch selection | Declining a branch switch left the selector pointing to the rejected branch | Re-render the selector from the actual active thread without replacing its draft |
| Late archive conflict | An old conflict callback could lock a later queued archive unlock | Only the originating vault epoch can invalidate its key/session |
| Stale operation failure | A rejected old asynchronous operation could replace the status of a newer/locked session | Scope operation and source-file failure updates to their original revision/project |

## Verification contract

The filesystem regressions use real temporary directories and files, symlinks,
hard links, an actual FIFO with a two-second reader deadline, and an ancestor
rename/replacement. External targets/replacement directories must remain intact.
Existing snapshot round trips, unchanged saves, append-only history, capacity,
identity and eight-writer conflict tests remain required. No lock file or snapshot
schema change is introduced. The Unix `libc` dependency already existed transitively;
its direct use is recorded in both dependency locks.

Real Chromium acceptance adds four transition regressions: rejecting a branch
change preserves selection/draft, declining unlock preserves unsent text and
state, and late failed configuration requests or source-file reads cannot change locked-session status.
The existing archive encryption/reopen, branches, model-transport fixtures and
isolated-code/network-sentinel tests remain required. Synthetic model responses
are transport fixtures, not evidence of actual model quality.

## Local results

- Three filesystem regressions failed as expected against the original baseline
  in a disposable source copy, then passed with this repair.
- Pinned Rust 1.85.0 full `scripts/run_gates.sh`: PASS, including format, locked
  builds/tests and the type boundary. All 14 workspace-integrity cases and six
  persistence-unit cases pass.
- Gateway `cargo test --locked`: 55 passed, one pre-existing ignored ENOSPC case.
- Studio state/encryption: 44 checks passed; research/chart: 31 checks passed.
- Deterministic HTML bundle, Python test syntax and workflow authority checks pass.
- Real Chromium transition and existing UI/lab witnesses run separately in CI;
  local Rust success is not claimed as browser validation.

## Boundaries

- Linux descriptor paths require procfs, as the existing request ledger does.
  Other Unix platforms retain no-follow/type/identity checks but use pathname
  child operations; descriptor-based ancestor isolation is a Linux guarantee.
- The directory is pinned for one operation, not for the lifetime of the public
  repository object. A deliberately replaced valid repository between separate
  operations is not authenticated by this mechanism.
- Advisory locking coordinates cooperating writers. These changes do not defeat
  an unrestricted host administrator, authenticate snapshots cryptographically,
  prove power-loss durability or add distributed filesystem guarantees.
- A concurrent atomic replacement may now cause a read to fail closed; callers
  should reload/retry rather than trust an inconsistent observation.
- A sync/verification error after rename can occur after data became visible.
  Reload or retry the same snapshot; an error is not a rollback receipt.
- No stored data are migrated or rewritten as a repair step. A rejected invalid
  storage entry requires operator investigation, not automatic relabeling.
- Cancelling an asynchronous UI operation prevents stale UI publication; it does
  not undo an already committed storage write or remote provider work.
