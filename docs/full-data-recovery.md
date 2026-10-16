# Offline full-data recovery

Status: DEVELOPMENT / UNSEALED

The workspace API export covers one workspace only. `scripts/data-snapshot.py`
captures all supported workspace files and the durable request ledger together.
It requires Python 3 and a local filesystem with file/directory fsync and hard
links. Restore additionally requires Linux, a libc exposing `renameat2`, and a
filesystem supporting `RENAME_NOREPLACE`. Unsupported restore platforms fail
closed without falling back to an overwriting rename. No extra dependency or
change to either pinned Cargo.lock is required.

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
publication uses atomic `RENAME_NOREPLACE`, so even a destination created after
the final absence check (including an empty directory or dangling symlink) is
preserved and blocks restore. It does not merge into, erase, or overwrite an
existing target. Backups likewise refuse existing output. Files use mode 0600 and
restored directories 0700. Ownership defaults to the caller unless `--owner`
is supplied. Use a destination readable by the gateway's runtime identity.

The destination parent must remain trusted and stable throughout maintenance;
this protects the final target name, not against a privileged actor replacing
ancestor directories or editing data. A pre-publication error removes only the
private staging directory and leaves the target absent (or preserves a racing
destination). If the parent-directory fsync fails after atomic publication,
restore returns failure but keeps the published, quarantined data: crash
durability is uncertain. Do not delete that directory or retry into it blindly;
inspect it offline. A retry rejects the existing target. No failure path resumes
traffic or creates core authorization.

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

## Inspect before restoring

Inspect an existing snapshot without restoring data or changing quarantine:

```bash
python3 scripts/data-snapshot.py inspect /secure/nexus-data.json
```

This command validates the same bounded archive contract as restore, then emits
one JSON summary with file/workspace counts, decoded byte count, captured
quarantine presence, and pending/indeterminate request counts. Empty and torn
request markers remain indeterminate. IDs, paths, per-file hashes and workspace
contents are omitted; aggregate counts can still be sensitive. Invalid archives
return nonzero with no success JSON. No destination, ownership change, offline
assertion or replay-risk acknowledgment is accepted for inspection.

`STRUCTURALLY_VALID` is not verification PASS: inspection does not revalidate core
audit history, authenticate the archive, establish its age/completeness relative
to the current volume, prove execution completion, or grant authority or Seal
readiness. The report explicitly leaves the recovery point unknown. A reported
absence of captured quarantine does not authorize writes; every restore still
adds quarantine. Use a stable private archive copy; inspection reads no live
volume and does not stop writers or prove an offline capture.

## Compare a candidate against a reference

```bash
python3 scripts/data-snapshot.py compare /secure/reference.json /secure/candidate.json
```

Both archives are fully structurally validated with the existing per-archive
64 MiB / 20,000-file bounds before any success JSON is emitted. The report gives
aggregate directional request/workspace differences, shared byte changes, shared
pending/indeterminate differences, and captured quarantine presence. No IDs,
paths, per-file hashes or workspace content are printed. Counts can still be
sensitive. Neither archive is modified; this command accepts no ownership,
offline or replay-risk acknowledgment options and never restores or resumes data.

`reference_ids_missing_from_candidate` counts IDs known to the reference but
absent from the proposed candidate. For requests, those missing IDs would not be
protected against duplicate admission by that candidate after explicit resumption.
Include indeterminate IDs in this assessment. Shared pending-to-indeterminate or
indeterminate-to-pending differences are reported, never automatically reconciled.
Workspace byte changes do not establish which history is legitimate or newer.

Reference and candidate are operator-selected roles, not inferred chronology or
trusted provenance. Zero differences, or an identical pair, do not establish a
current/full backup, absence of all replay risk, equivalent core history, completed
execution, authenticity, authority, verification PASS or Seal readiness. Requests
missing from both archives remain invisible; the recovery point stays unknown.
Compare stable private copies and interpret the report alongside independent
knowledge of their origin. Every actual restore still reinstates quarantine.

## Restore quarantine and explicit resumption

Every restore writes `.nexus-recovery-required` before publishing the directory.
The current executable latches its presence at startup. All mutating gateway
routes then return 503 `recovery_acknowledgment_required` before body parsing,
reservation or delegation. Authentication still runs first (401 without a valid
bearer token). Authenticated GET remains available for recovered request status
and workspace inspection. A normal process restart does not lift quarantine;
removing the marker from a running process does not lift its latched gate either.
Any marker object, including an empty file or dangling symlink, blocks writes;
unexpected metadata errors block startup.

Successful verification, checksum validation or attestation never resumes traffic.
If an operator explicitly accepts the remaining post-snapshot replay risk, stop
all writers, then run:

```bash
python3 scripts/data-snapshot.py resume /recovery/data --offline --acknowledge-replay-risk
# Restart the gateway afterward; its transport and core authorization still apply.
```

`resume` validates the expected marker, unlinks it and syncs the data directory.
It never deletes request markers or workspace files, replays requests, or creates
an AuthorizedRequest. Existing corrupt/symlink markers cannot be cleared through
this tool. Backing up a quarantined volume preserves the marker; restoring even a
previously resumed volume always reinstates quarantine. OS access remains trusted:
a privileged actor can delete files or run an older binary. Raw filesystem copies
and the legacy one-workspace API import do not acquire this new restore protection.
Liveness/UI GET can remain healthy during quarantine; write availability is
explicitly signaled by 503, not inferred from the root page returning 200. Public
`/readyz` also returns 503 until resumption and restart, while `/livez` remains 200;
see [the probe contract](gateway-health.md).

This interlock prevents accidental admission from restored state. Acknowledging
risk does not repair lost IDs, prove a zero-loss recovery point, or confer core
execution authority. No second person or paid provider is required: CI exercises
the full pause/inspect/restart/explicit-resume cycle automatically on synthetic data.

## What recovery proves

Captured accepted request IDs remain `pending` and duplicate POST returns 409.
Captured empty/torn markers remain `indeterminate`, also rejecting duplicates.
During quarantine POST returns 503 instead of admitting anything; after explicit
resumption captured duplicates again return 409. They are never replayed.
`pending` proves recorded acceptance, not completed work. After explicit resumption,
new requests and workspaces remain writable through a further restart.

**Snapshot age bounds replay protection.** Requests admitted after the snapshot
are absent from it and can be admitted again after recovery. Tests include that
counterexample explicitly. This is no zero-loss or exactly-once guarantee, no
continuous backup service, and no durable executor-outcome journal. Production
recovery must account for the snapshot's recovery point before accepting traffic.

CI uses a dedicated synthetic RUNNER_TEMP directory, stops the container, captures
a real workspace plus accepted and uncertain request markers, admits a further ID
after capture to expose the recovery-point gap, then destroys only that
witness, restores with the runtime owner, and checks live authenticated HTTP after
restore and another restart. Unit tests reject malformed/unsafe archives and
preserve existing destinations. The static gate checks that this witness remains
isolated; actual workflow execution is required for a current verification claim.

Evidence is not authority. Recovery never constructs `AuthorizedRequest` or grants
execution permission. `A_out ≤ A_in`, CT-001..020, Bootstrap versus Verify separation
and both pinned Cargo.lock files remain required. Verification evidence does not
constitute a new Seal, production deployment, or independent attestation claim.
