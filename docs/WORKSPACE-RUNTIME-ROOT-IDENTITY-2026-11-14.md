# Runtime workspace-volume identity: prevent silent data-root substitution

Date: 2026-11-14
Baseline: `b7855b1a1bb9f3776e8f24b682d124cbe334543e`
Authority: **unmerged draft code / disposable test evidence only**

## Confirmed source defect

The real Rust gateway constructs `FileWorkspaceRepository::new(data_root)`
and reopens the configured pathname on **every** workspace request.
`SnapshotDirectory` holds a file descriptor for the duration of one
individual operation, so it protects that operation against TOCTOU attacks,
but no descriptor pins the backing directory across multiple operations.

If the actual data-root path is moved/unmounted and another directory
appears under the same path, the next read can return a false 404 and a
new workspace create/import can write a second, inconsistent history into
that replacement directory. The request-ledger's separate directory pin is
not sufficient protection for workspace-specific routes.

## Applied repair

- Provide an optional `FileWorkspaceRepository::pin_root()`. It opens and
  retains a descriptor to the original workspace root at startup.
- For pinned repositories, verify both the root's path identity and the
  per-operation opened directory against the retained identity, and do
  not automatically create missing directories after startup.
- Make the real gateway's `CoreDelegate::new` pin the workspace root
  **before it starts the listener**; fail startup if it cannot pin.
- Preserve existing short-lived repository behavior for library consumers
  that explicitly use `FileWorkspaceRepository::new` without pinning.
- Test moving the original ancestor, inserting a writable substitute,
  attempted reads and writes, a symlink alias to the moved original
  directory, and restoration of the original directory inode. The
  substitute's sentinel remains untouched.

## Limits and self-critique

Pinning detects path substitution; it does not detect disk-full,
short writes, corruption in unrelated workspaces, an inaccessible
remote host, or an attack by a privileged actor against the exact pinned
directory. Filesystem operations may block on the kernel or remote
storage. A read after repair still needs valid snapshot and audit-chain
checks, enforced separately by the repository. No synthetic test
asserts an actual provider mount was lost, and no production data was
moved. The startup pin does not itself prove a volume was mounted
correctly **before** gateway startup.

This patch changes `src/workspace_persistence.rs`, which is also
touched by the unmerged feature stack #129–#134. Those branches
must be reconciled deliberately, not overwritten.

## Release constraint

Draft only. Do not merge to `main`, deploy to Render, or assert
Stage D until automatic deployment is controlled, strict main-base
status checks are enabled, and independent provider recovery proof
is accepted. Require exact-head Rust/HTTP/CI verification first.
