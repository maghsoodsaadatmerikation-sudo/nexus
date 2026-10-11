# Offline full-data recovery

Status: DEVELOPMENT / UNSEALED

The workspace API export covers one workspace only. `scripts/data-snapshot.py`
captures all supported workspace files and the durable request ledger together.
It requires Python 3 and a local filesystem with file/directory fsync and hard
links. No extra dependency or change to either pinned Cargo.lock is required.

## Contract

Stop every gateway/writer using the data directory before backup or restore.
Keep maintenance exclusive until completion. `--offline` is the caller's explicit
assertion of this condition, not a process lock or automatic shutdown. File-change
checks cannot establish a consistent snapshot while other writers are active.
Use one gateway process per directory; network/shared filesystems are unsupported.

```bash
# All writers must already be stopped. Existing destinations are rejected.
python3 scripts/data-snapshot.py backup /data /secure/nexus-data.json --offline
python3 scripts/data-snapshot.py restore /secure/nexus-data.json /recovery/data --offline
# Container runtime UID/GID is 10001:10001; changing ownership needs OS privilege.
sudo python3 scripts/data-snapshot.py restore /secure/nexus-data.json /recovery/container-data --offline --owner 10001:10001
```

The backup must reside outside the source directory. Its parent must exist.
Restore stages validated files in the destination's existing parent, syncs them,
and publishes the directory only after validation. The target must be absent;
it does not merge into, erase, or overwrite an existing target under exclusive
maintenance. Backups likewise refuse existing output. Files use mode 0600 and
restored directories 0700. Ownership defaults to the caller unless `--owner`
is supplied. Use a destination readable by the gateway's runtime identity.

The versioned JSON envelope records paths, byte sizes, SHA-256 digests and base64
contents. It accepts only current hex-named workspace JSON and request marker
files. Symlinks, unknown files (including unfinished `.json.tmp` writes), path
traversal, duplicates, corrupt markers, inconsistent sizes/digests and archives
over 64 MiB or 20,000 files fail closed. The gateway retains core workspace audit
validation on load; the snapshot tool's structural checks do not replace it.

Archives contain plaintext private workspace data. Protect them with appropriate
storage/access controls; this tool does not encrypt, sign or authenticate them.
SHA-256 detects inconsistent bytes, not malicious replacement with recomputed
hashes. Environment configuration and bearer tokens are not captured by the tool;
workspace content itself can contain sensitive data. CI never uploads the raw
synthetic data archive as release evidence.

## What recovery proves

Captured accepted request IDs remain `pending` and duplicate POST returns 409.
Captured empty/torn markers remain `indeterminate`, also rejecting duplicates.
They are never replayed. `pending` proves recorded acceptance, not completed work.
New requests and workspaces remain writable after restore and a further restart.

**Snapshot age bounds replay protection.** Requests admitted after the snapshot
are absent from it and can be admitted again after recovery. Tests include that
counterexample explicitly. This is no zero-loss or exactly-once guarantee, no
continuous backup service, and no durable executor-outcome journal. Production
recovery must account for the snapshot's recovery point before accepting traffic.

CI uses a dedicated synthetic RUNNER_TEMP directory, stops the container, captures
a real workspace plus accepted and uncertain request markers, destroys only that
witness, restores with the runtime owner, and checks live authenticated HTTP after
restore and another restart. Unit tests reject malformed/unsafe archives and
preserve existing destinations. The static gate checks that this witness remains
isolated; actual workflow execution is required for a current verification claim.

Evidence is not authority. Recovery never constructs `AuthorizedRequest` or grants
execution permission. `A_out ≤ A_in`, CT-001..020, Bootstrap versus Verify separation
and both pinned Cargo.lock files remain required. Verification evidence does not
constitute a new Seal, production deployment, or independent attestation claim.
