# Phase 28 — Offline operator data + finished-journal restore (CI pilot)

**Scope:** New standalone explicit-operator Python 3.13/Linux snapshot script and
disposable two-container acceptance. This is not an independent hosted
custodian, signed release, encrypted backup, autonomous recovery service, or
proof of power-loss survival. PR #244 remains Draft.

## Why this addresses an executable blocker

The Phase 27 child-process test retained the original local filesystem while
the daemon was SIGKILLed and restarted. That tests a **process restart**,
not loss of the original workspace storage. Phase 28 adds an intentionally
narrow offline snapshot containing the allowlisted workspace file tree,
empty directories, canonical manifest and *finished* one-use approval
receipts. A recipient can restore to a **new empty owner-private root**
without restarting any approved task.

This is an operator-controlled command rather than a browser or model tool.

## Operator commands (only for a trusted, stopped local operator)

Use the separate standalone source script (not part of the distributable
pilot ZIP) from a reviewed checkout. The script runs only under a nonroot
Linux user with a private 0700 root and private 0700 backup parent.

Export existing workspace **after halting any service and other writers**:

~~~bash
python3 -I -B scripts/nexus-operator-snapshot.py export \
  --root /private/operator-root \
  --workspace acceptance \
  --archive /private/backup/operator-acceptance.zip \
  --approve-offline-export
~~~

Securely transfer the resulting archive, separately obtain and verify its
SHA-256 from a trusted transport or channel, and restore **only to a clean,
previously existing, user-owned 0700 root**:

~~~bash
python3 -I -B scripts/nexus-operator-snapshot.py restore \
  --root /private/empty-recovery-root \
  --workspace acceptance \
  --archive /private/backup/operator-acceptance.zip \
  --expected-sha256 TRUSTED_ARCHIVE_SHA256 \
  --approve-offline-restore
~~~

Neither operation starts code or a socket service. An existing destination
root with any content is rejected. The SHA check covers exact archive
bytes and *does not* authenticate the publisher or operator. A hostile
same-UID process, compromised source, improper external SHA pin, unsafe
transport, malicious archive source or offline tampering of both backup and
digest are not excluded by this proof.

**Sensitive data:** this initial archive is **not encrypted** and can contain
all workspace file contents, so do not use it for private or production
data without separately approved encryption, key management and access
controls. Never upload a real archive to GitHub CI. CI uses hard-coded,
disposable synthetic bytes only.

### Safety checks implemented

- No live auto-retry. Only **finished** local journal records are eligible.
  A started, corrupt, extra or quarantined journal is denied.
- Audit the original workspace and per-file SHA-256 before archiving.
  Single-use journal data and original exact workspace manifest digest are
  included; archive entries use stored ZIP data with explicit fixed modes.
- Read archive once through a no-follow bounded file descriptor, require
  independent expected SHA-256, reject duplicates, symlinks, compression,
  traversal, invalid JSON schema and unexpected entries. Validate **all**
  expected file contents and journal digests *before* creating the restored
  workspace, then write with owner-only file modes and fsync the journal.
- Recompute workspace manifest and all receipts after restoration, preserve
  the consumed approval history and refuse overwriting a restored root.
  **Filesystem failure during writing may leave a partial, quarantined
  destination that requires manual inspection; there is no automatic cleanup.**

### CI — three separate Docker volumes

A dedicated workflow, operator-volume-recovery.yml, pulls a disposable Python
image, resolves its exact immutable SHA-256 *for that CI execution*, and
exercises the actual snapshot tool via two separate unprivileged, no-network
Docker container runs. Each container receives its own state volume; a
separate transfer volume holds the synthetic archive.

1. Create synthetic workspace and **finished one-use journal** in SOURCE.
2. Export the offline snapshot to TRANSFER with a whole-archive SHA.
3. Delete SOURCE volume **before** creating/restoring the recovered workspace.
4. Deny incorrect digest, then deny a modified ZIP even if a newly computed
   whole-archive digest is passed. Both failures must leave RECOVERY empty.
5. Restore from unmodified TRANSFER into empty RECOVERY. Verify workspace
   digest, the original finished journal, denial of exact-digest replay,
   absence of auto-start and refusal to restore over an existing root.
6. Destroy all disposable volumes and report bounded JSON without user data.

**Evidence classification:** this tests destruction of one Docker volume
while retaining a separate Docker backup volume on the same **single CI
host**. The same Docker daemon and GitHub Actions account control the
entire process. It is *not* an independent off-host backup, separate admin,
host reboot, full disk loss, provider-level recovery, SSH custodianship,
source-signature verification, or permission for public deployment.

## Further gate before release

For actual durable operation, require independently controlled backup
storage, encrypted transport/storage with an explicit key recovery scheme,
authenticated source/publisher identity, crash-consistent snapshots of
running applications, retention/rollback policy, a separate boot/reboot and
disk-loss experiment, a live-orphan audit, and independent witness receipts.

Respect authority invariant A_out <= A_in; preserve PR #244 in Draft until
exact-head CI has passed and independent operator review authorizes change.
