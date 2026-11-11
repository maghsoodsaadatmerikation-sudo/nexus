# Stage D: private off-host volume intake (current recovery gate)

**Status: not yet executed on the production volume.** This is a procedure for
a future **separately downloaded copy** of the Railway data, not a backup,
restore, service deployment, or live-state verification. Never commit the copy,
snapshot, manifest, token, or workspace records to this public repository.

## Exact currently observed identity (2026-11-10)

- Railway project: `2ac7887b-d67a-48be-8a7b-bd54092893ae` (`NEXUS Stage D`)
- Service: `0032fc74-2c52-475d-b9df-9dca59237d93` (`nexus-stage-d`)
- Deployment: `db2fd959-918e-49d5-b077-1ac74fac9a82` (SUCCESS in last connected read)
- Deployed source commit: `3c0977f4c7fc9fb5e9a78bdb1eeb581cb3cb4959`
- Attached `/data` volume: `cc47a350-6c7e-4487-89d9-c4b390f94884` (`nexus-data-lMm1`)
- The GitHub observer commit is **not** the deployed source commit.
- Public Runtime Identity and unauthenticated/invalid-Bearer checks PASS;
  they do not prove that any workspace data is recoverable.
- Prior dashboard check reported **No Backups**; current file contents and
  data-retention status have not been independently established.

## Export boundary (not executed)

Railway documents `railway volume files download` for files **and
directories**, or file access through an active service. Only an authenticated
operator session with access to the exact Railway project, service and volume
can perform the export. Re-check `railway volume files --help` against the
installed CLI version before choosing a destination.

1. Select the exact production project/environment/service and confirm the
   mounted volume ID. **Do not** detach, replace, resize, delete, redeploy,
   or restart the original service. Do not invoke provider backups/restore.
2. Download the volume's data directory to a **separate private storage
   destination** that is not the Railway volume, this Git checkout, a public
   Actions artifact, or a public cloud bucket. Keep all credentials local to
   the operator session. Record the provider export event/time privately.
3. Do not claim a consistent point-in-time snapshot merely because the
   download completed. Files can be copied at different moments while the
   application is active. Verify consistency using a maintenance/offline
   capture or a provider-supported atomic snapshot before relying on it.

## Directory-fd scope and external hard-link rejection (2026-11-11)

The offline `data-snapshot.py` backup and direct private copy intake now use
a **single bounded source scanner**. It opens the copied data root and its
`requests/` ledger as Linux directory file descriptors with
`O_DIRECTORY | O_NOFOLLOW`, reads each workspace or marker with a
dirfd-relative `O_NOFOLLOW` open, and checks that its source and ledger
directory names/inodes/metadata stayed stable over the scan. Snapshot
file reads reject hard links (`st_nlink != 1`), symlinks, special files,
unexpected paths and in-flight per-file metadata changes. An
operator-supplied private copy is checked by the *same* scanner on each
pre/post-archive pass, not by an independent path-string walker.

**Why it matters:** the exact-target Railway CLI wrapper already rejected
hard links on its initial downloaded directory; the standalone
`verify-offhost-volume-export.py` entry point previously trusted any
regular-looking file with a valid NEXUS filename, including a hard link to
a file outside the intended export. A replacement of `requests/` between
the initial path check and a subsequent pathname open could also redirect
a weak source scanner. The current scanner binds opens to anchored
directory descriptors and rejects directory replacement.

Disposable regression tests explicitly attempt a hard-linked external
workspace, a hard-linked external request marker, a hard-linked archive,
a `requests/` symlink swap after scanning starts, and a source file
created during the scan; all must refuse a successful snapshot or private
receipt. The standalone private intake tests independently require
rejection before a receipt directory is published.

**Self-critique and limits:** a clean scan is still **not** a
point-in-time-consistent snapshot of a live Railway writer; a file could
change after its individual read. Directory metadata checks are bounded
observations, not an adversary-resistant filesystem snapshot. Linux
directory-descriptor semantics are required. This restriction may reject
operator copies prepared using intentional hard links; they must be
re-exported as distinct regular files, not accepted by relaxing the rule.
Neither the original Railway data nor a provider-native backup was read,
altered or independently recovered. No release authority or Seal follows.

## Private intake of a copied directory

From the repository checkout, with the copied data directory stored
**outside the checkout and outside the original volume**:

```bash
python3 scripts/verify-offhost-volume-export.py \
  --export-root /private/copied-data \
  --private-evidence-dir /private/stage-d-intake \
  --volume-id cc47a350-6c7e-4487-89d9-c4b390f94884 \
  --deployment-id db2fd959-918e-49d5-b077-1ac74fac9a82 \
  --runtime-commit 3c0977f4c7fc9fb5e9a78bdb1eeb581cb3cb4959
```

The destination must not already exist. **New local-copy drift gate:** the
tool independently reads the operator-held copied directory **before** its
snapshot, compares every path/byte-length/SHA-256 to the archive's validated
content, and reads the directory again **after** the quarantined restore.
Any changed, added, deleted, missing or symlinked data file/request marker
prevents a successful report. This closes an important earlier false-positive
possibility in which archive contents round-tripped perfectly even though
the *input copied directory was changing during intake*. A private PASS
report now includes `local_copy_scans_matched_archive=true` but still marks
`source_consistency=not_verified`.

The comparison is **not** a consistent Railway backup: the copied directory
might already contain mixed versions from a live file-by-file download,
changes may occur then revert between scans, and new changes could occur
after the last check. This gate proves only matching observed bytes of the
**local operator-held copy** across this bounded rehearsal window. Do not
mistake it for source provenance, an atomic remote point-in-time capture,
or independently recoverable off-provider custody.

The tool uses the existing
`data-snapshot.py` offline format and its validation rules, creates a
SHA-256-addressable private archive, inspects its structure, exercises an
isolated restore, compares recovered file bytes, and requires a
`.nexus-recovery-required` quarantine marker. It does **not** resume the
restored state or start a server. Files stay local with private directory
permissions; the process does not upload or deploy anything.

An output of `STRUCTURAL_REHEARSAL_PASS` **only** certifies that the
operator-supplied copy was structurally valid and exercised an isolated
byte round-trip. Even then, the report explicitly marks volume origin,
capture consistency, live recovery, and a real independent Railway backup
as *unverified*. Never convert that label to Stage D COMPLETE.

For additional defense, place the downloaded archive and the private
intake directory on independent storage and verify the recorded SHA-256
from that copy. Use `data-snapshot.py inspect` to revalidate integrity.

## Optional Rust semantic audit — current-source compatibility check

The private intake may additionally validate the quarantined restored
workspace files with **the real Rust durable-workspace repository loader**.

**Pre-audit source-revision guard (added 2026-11-11):** For the observed
Railway deployed source `3c0977f4c7fc9fb5e9a78bdb1eeb581cb3cb4959`, the
public Git object identities of `src/workspace.rs`,
`src/workspace_persistence.rs`, `src/epistemic.rs`,
`src/analysis.rs`, and `rust-toolchain.toml` were separately compared
with the repository checkout. These selected files are byte-identical to
the observed deployed *source commit*. Before any optional Rust-audited
private intake creates its evidence directory, an **offline fail-closed**
preflight `scripts/stage-d-core-parity.py` checks the same pinned Git
blob identities from local files and rejects unsupported supplied runtime
commits or local code changes. Success is recorded privately as
`rust_core_source_parity: pass_selected_pinned_git_blobs`.
Without the Rust audit it is `not_evaluated`. This is **selected-file
source parity only**: the complete crate, Cargo lock, other code,
compiled validator executable and binary actually running on Railway are
*not* asserted identical or independently attested. The deployed commit
string itself is still operator-supplied metadata, not a provider identity
proof. For a future deployed revision, derive and independently review a
new bounded source map; do not treat an unsupported runtime revision as
corrupt data. The structural-only path remains available without a
Rust semantic compatibility claim.

The **separate optional Rust loader**, not the source-parity preflight,
is stronger than JSON/schema/SHA-256 structure alone: it checks ordered
audit events, presence of provenance, correspondence between claims,
alternatives and their events, and explicit human-judgment transitions.
The program is `src/bin/nexus-private-core-audit.rs`; it is compiled
against the **current repository's pinned Rust source** (not against a
remote production binary). It performs read-only, bounded directory scans
and prints no paths, decisions, identifiers or data.

On a trusted private operator machine, after obtaining the *separate*
operator-held copy and building this repository's Rust validator:

```bash
cargo build --locked --bin nexus-private-core-audit
python3 scripts/verify-offhost-volume-export.py \
  --export-root /private/copied-data \
  --private-evidence-dir /private/stage-d-semantic-intake \
  --volume-id cc47a350-6c7e-4487-89d9-c4b390f94884 \
  --deployment-id db2fd959-918e-49d5-b077-1ac74fac9a82 \
  --runtime-commit 3c0977f4c7fc9fb5e9a78bdb1eeb581cb3cb4959 \
  --rust-validator-bin ./target/debug/nexus-private-core-audit
```

The validator is **optional** for the earlier structural-only mode:
without it the receipt MUST state `rust_core_audit: not_evaluated`.
With an operator-supplied binary that successfully validates every
workspace, the private report states
`rust_core_audit: pass_operator_supplied_rust_binary` and
`rust_core_binary_identity: operator_supplied_unverified`. A failing Rust
audit stops the successful receipt. **After** the Rust subprocess returns,
the intake rechecks the entire local source copy (path set, lengths,
SHA-256) against the archived bytes, confirms the private archive's own
SHA-256 is unchanged, **and** rechecks the isolated restored directory
layout, exact file bytes and recovery-required quarantine marker. Only
then can it write the receipt; the private field
`post_rust_source_archive_and_restore_rechecked=true` records this bounded
post-audit observation. Without Rust this field is false/not applicable.
Synthetic negative tests deliberately mutate the local copy, a recovered
workspace, the archive, or the quarantine marker after Rust succeeds and require a
blocked receipt. The archive's original SHA-256 is also checked again at
receipt time in structural-only mode; a post-restore archive mutation cannot
silently become a new successful snapshot digest. This additional witness does *not*
cryptographically identify or attest the compiler, the original production
source revision, provenance, original-file consistency or the provider.
The selected source files above currently match the pinned deployed
revision, but differences in the rest of the crate or dependency lock and
an independently unverified executable leave real deployment-binary
compatibility unproven. A future source change may make an offline audit
reject older valid files; incompatibility is NOT evidence of real data
corruption. Keep the original copy private and unchanged.

A disposable CI job validates this exact implementation using synthetic
well-formed workspaces and negative fixtures for invalid audit sequence,
unaudited claims, unaudited human judgment, missing provenance and
unsafe validator paths. It does not fetch or publish live private data.

## Fail-closed next gate

Before live replacement/survival tests, obtain (a) independently verified
origin and point-in-time consistency of the original volume copy, (b) an
operator-held backup outside Railway with verified checksum, and (c) an
isolated test proving the backed-up data is usable. Then execute the
existing exact-commit `docs/STAGE-D-EVIDENCE.md` protocol. Authenticated
workspace witness, replacement survival and destructive absence/restore
have not been tested against the current production deployment.

No payment, Seal, promotion, authorization expansion, or claim of
production readiness follows from this procedure. `A_out <= A_in`.
