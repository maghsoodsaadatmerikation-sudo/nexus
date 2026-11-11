# Stage D — Rust request-ledger filesystem boundary

**Status:** a defensive Rust code change and synthetic regression tests, not a deployment or a Railway data recovery.

## Verified recovery semantics preserved

The original request ledger source `artifact-05/src/request_store.rs` and the offline Python `scripts/data-snapshot.py` both accept `pending\n` as **Pending**, and every prefix of those eight bytes (including a zero-byte legacy file and the reserved `p`) as **Indeterminate**. This is deliberate: a crash during the initial reservation or final durable write cannot be interpreted as acceptance, and the request cannot be blindly replayed. Arbitrary bytes and overlong markers are invalid. **Do not tighten this to only complete `pending\n`: that would reject legitimate crash recovery states.**

## Vulnerability class addressed

Rust `RequestStore::open` previously inspected a directory entry and then independently reopened that pathname using `fs::read`. `pending()` likewise opened the existing marker using a normal path open. A filesystem writer capable of replacing or hard-linking request markers could create an alternate inode or a symlink after a preliminary metadata check; the gateway might read or write the substituted file. The existing Python Stage D snapshot scanner already rejects external hardlinks and uses no-follow directory-relative opens. The Rust startup/write path needed comparable **final-component** protections.

## Implemented

- Use `OpenOptions` with `libc::O_NOFOLLOW | libc::O_NONBLOCK` so a replaced final symlink and a substituted FIFO do not become ordinary file reads/writes.
- Validate `symlink_metadata` and the actually opened inode's device/inode, regular file type, single hardlink and maximum eight-byte length before use; bound reads to at most nine bytes. Recheck inode/size/mtime/ctime after the read and recheck the path identity before accepting a recovered status.
- Reject a symlink at the ledger-root final component at startup. Keep the existing durable sync sequence and request-status semantics unchanged.
- Reject attempts to mark a hardlinked or replaced symlink marker Pending before modifying the target; no change to delegation policy, human authority or release lifecycle.
- Add six direct Rust tests: all nine legal crash prefixes, illegal/overlong marker strings, external hardlink rejection on startup, pending write through hardlink denial, pending write through symlink denial, and normal reserved-to-pending lifecycle.
- Run the actual Rust tests in Stage D CI under the pinned toolchain with `--locked`; add direct `libc` to the existing pinned `artifact-05` lockfile. No external runtime or paid service is introduced.

## Limits and self-critique

The November 11 safeguard covered the **final file component** only. The November 12 follow-on below pins the directory descriptor and prevents an ancestor rename or replacement from redirecting ordinary request reads/writes; it remains insufficient against an attacker who can modify files **inside that pinned directory**, manipulate the host process or file metadata, or swap a marker just after the final check. Strong ownership, permissions and a single trusted writer on `/data/requests` remain necessary. The checks do not prove atomic provider backups or authenticate the entire filesystem. A successful Rust test is not a production-capture or recovery witness.

The change has **not** been deployed to the pinned live Railway runtime. The original Volume `cc47a350-6c7e-4487-89d9-c4b390f94884` has not been accessed or mutated. No token, release, Seal, restart or new charge. Issue #70 stays OPEN; `A_out <= A_in`.

## November 12 follow-on: pinned original ledger directory (PR #98)

The earlier protection correctly refused substituted **marker** symlinks and external
hardlinks, but request creation and final Pending writes still passed a mutable
absolute root pathname to the operating system. A renamed `requests` ancestor
or substituted directory could therefore redirect a later operation.

The Rust `RequestStore` now owns an opened **Linux directory File Descriptor**
for its entire lifetime. It opens `requests` with
`O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC`, checks the opened device/inode against
the visible path, and enumerates entries and opens/creates markers beneath
`/proc/self/fd/<directory-fd>/`. The latter is a Linux-specific, fd-bound
directory reference available in the actual Railway Linux container and
GitHub Linux CI: it tracks the **original inode**, not a subsequently substituted
path. Both before and after mutation, the code requires the original directory's
device/inode still to occupy the expected visible root path.

- `reserve()` creates a unique marker relative to the pinned directory,
  syncs the new file and the **same opened directory**, checks the final
  file's identity/length, and refuses success if the root was replaced.
- `pending()` opens the existing marker relative to that directory with
  `O_NOFOLLOW | O_NONBLOCK`, syncs the complete marker, rechecks file identity
  and length, and refuses success if the visible root was replaced.
- Startup enumerates the pinned directory and refuses success if the expected
  root no longer resolves to the same inode after reading markers.
- Rust regressions rename the ledger directory and separately rename an
  ancestor **after** the store opens, replace the path, then demonstrate that
  attempts to reserve or mark Pending fail without modifying either displaced
  original or substituted data. A startup symlink alias is also rejected.
  Existing legal interrupted-write and replay-avoidance semantics remain
  unchanged.

The `/proc/self/fd` design requires a Linux host with procfs mounted. If it is
absent or inaccessible, the store **fails closed** rather than using a
pathname fallback. Directory pinning narrows a real filesystem race but is not
proof of privileged host integrity, exact history, external backup custody,
or the absence of a hostile writer **inside** the ledger. No new network
service, provider token, product deployment, mutable Railway volume access,
paid infrastructure, release or Seal is involved. `A_out <= A_in`.
