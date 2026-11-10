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
This is stronger than JSON/schema/SHA-256 integrity alone: it checks ordered
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
audit stops the successful receipt. This additional witness does *not*
cryptographically identify or attest the compiler, the original production
source revision, provenance, original-file consistency or the provider.
The current main Rust version may differ from the pinned deployment
revision and reject valid earlier formats; incompatibility is NOT evidence
of real data corruption. Keep the original copy private and unchanged.

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
