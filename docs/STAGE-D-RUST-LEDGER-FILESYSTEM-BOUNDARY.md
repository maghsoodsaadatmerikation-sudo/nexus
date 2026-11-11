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

This is **not** a complete defense against an attacker who can rewrite an ancestor directory, exploit same-size in-place modifications with filesystem timestamp manipulation, or compromise the service process. The path name is not anchored by a directory FD as in Python's read-only snapshot scanner. Strong ownership, permissions and a single trusted writer on `/data/requests` remain necessary. The checks reduce accidental/malicious marker aliasing; they do not prove atomic provider backups or authenticate the entire filesystem. A successful Rust test is not a production-capture or recovery witness.

The change has **not** been deployed to the pinned live Railway runtime. The original Volume `cc47a350-6c7e-4487-89d9-c4b390f94884` has not been accessed or mutated. No token, release, Seal, restart or new charge. Issue #70 stays OPEN; `A_out <= A_in`.
