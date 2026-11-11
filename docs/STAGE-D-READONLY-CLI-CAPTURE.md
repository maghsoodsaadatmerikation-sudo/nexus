# Pilot 04 — exact-target, read-only Railway CLI copy gate

**Status as of 2026-11-10: implemented and synthetic-tested; no real
production copy or offsite backup has been performed.** This document is a
specific next step beyond
[private off-host intake](STAGE-D-PRIVATE-EXPORT-INTAKE.md). A successful dry
run or CI mock never closes Stage D or Issue #70.

## Why a provider snapshot alone cannot close this issue

Railway offers manual and scheduled backups of mounted volumes, but its
[documented restores](https://docs.railway.com/volumes/backups) are only to
the **same project and environment**, and incremental backup storage is
metered. This gives one recovery route but not an independent, off-provider
copy. Railway's
[documented CLI](https://docs.railway.com/cli/volume) supports the separate
read-only operation `railway volume --project <PROJECT> --environment <ENV> --service <SERVICE> files --volume <VOLUME> download / <PRIVATE_DEST> --concurrency 1`.
A directory download is NOT a consistent point-in-time snapshot when
writers remain active; source identity and consistency need independent
evidence.

## Exact original host target — verified through connected Railway read

- Project `2ac7887b-d67a-48be-8a7b-bd54092893ae`
- Production environment `56c4bc45-0e62-4aa9-832f-884bb1aa620c`
- Service `0032fc74-2c52-475d-b9df-9dca59237d93`
- Original volume `cc47a350-6c7e-4487-89d9-c4b390f94884`, mount `/data`
- Last known deployment `db2fd959-918e-49d5-b077-1ac74fac9a82`
- Last known pinned source `3c0977f4c7fc9fb5e9a78bdb1eeb581cb3cb4959`

All identifiers are hardcoded in
`scripts/capture-railway-volume-readonly.py` to prevent accidental
selection of a lookalike production service. Reconfirm all of them
independently before a *real* attempt: the code does not have privileged
provider identity attestation. If the original volume or deployed revision
has changed, stop and review it, rather than updating a UUID by guess.

## Pilot 07: real Railway CLI parser (not a fake provider)

The earlier Stage D capture tests used a **local fake CLI**. A fake proves
our own validation and fail-closed behavior, but it **does not verify
Railway's actual option ordering, flags or version compatibility**.

`.github/workflows/stage-d-private-volume-intake.yml` now has an independent
`real-railway-cli-readonly-grammar` job. It downloads the official **Railway
CLI v5.71.0** Linux binary from a fixed GitHub Release, verifies that the
archive SHA-256 is exactly
`2e682fd2ddf8d6fdf9e46d9d99d99646ff0022a6abb0c2bca93011348a269fb9`,
extracts only the expected `railway` executable into a private CI temp
directory, and asks the **real parser** for `--version` and `--help`.
This genuine CLI test **caught and fixed an operational bug**: the original
helper placed `--project`, `--environment` and `--service` before the `volume`
subcommand, causing the real CLI to exit with argument error code 2. The
corrected invocation places those three flags *on the `volume` command*,
then `files --volume <ID> download / <DEST> --concurrency 1`. The real CLI
parser now accepts it. The old fake-only tests could not have detected this. The binary's auto-update is disabled. CI
contains no real Railway credentials and deliberately never performs a
volume list, files read, backup creation or download.

The execution tool itself now checks the **same pinned version and help
grammar before creating its local output directory**. If the operator's
installed CLI has been upgraded, its compatibility must be re-reviewed and
the pin deliberately updated. This is a security and repeatability control,
not an instruction to downgrade a shared installed CLI blindly.

**Even a real CLI parser PASS is not a production volume copy, remote
authentication check, consistency guarantee or recovery proof.** It closes
only the *local invocation syntax* uncertainty. The original volume
and server remain untouched.

## Additional optional Rust durable-audit check

With the exact current-source Rust audit binary built on a trusted
private machine, the operator can opt into a semantic audit of the
quarantined restored copy by adding
`--rust-validator-bin /absolute/path/to/nexus-private-core-audit`
to the private capture command. The private intake/receipt then records
either `pass_operator_supplied_rust_binary` or `not_evaluated`. The
Rust check verifies workspace audit events and explicit human judgment
against the current core's durable file loader, not simply JSON syntax.
Invalid history blocks a semantically audited receipt. It does not prove
the supplied binary's independent identity, the original deployed Rust
revision, atomic Railway capture, live provider recovery or offsite custody.
The original `nexus.data-snapshot.v1` archive remains an **unencrypted
private copy** and must not be uploaded to a public CI artifact.

## Two modes — plan first, execute only from trusted private environment

Dry run (no credentials, no network, no directory created):

```bash
python3 scripts/capture-railway-volume-readonly.py \
  --private-root /home/operator/private/nexus-stage-d-capture
```

Actual read-only capture (not yet authorized or executed here):

```bash
# In a trusted environment with a Railway CLI installed and logged in,
# provide the CLI's authenticated token by a secure secret mechanism.
# Never put this token or downloaded data into an issue, chat, GitHub job log,
# public Actions artifact, public repo, or connected public storage.

python3 scripts/capture-railway-volume-readonly.py \
  --private-root /home/operator/private/nexus-stage-d-capture \
  --railway-bin /usr/local/bin/railway --execute
```

The explicit `--execute` mode requires `RAILWAY_TOKEN` or
`RAILWAY_API_TOKEN` to be set in the operator's private process environment
**before invocation**. Do not place tokens in the command line or share them
in chat. Actual Railway CLI login/permissions and source volume identity must be
checked in the private environment. The CLI syntax was tested on the exact
pinned v5.71.0 build; different versions are rejected until reviewed.
If that check fails, stop; never fall back to a mutation or another volume.

The tool creates a new private `0700` directory **outside the public Git
checkout**, invokes **only** the documented
`volume files --volume <exact ID> download / <private dest>` command with
concurrency 1, then checks that the copied tree contains regular non-linked
files. It invokes the existing offline
`verify-offhost-volume-export.py` intake to build and inspect a private
snapshot, rehearse a quarantined isolated byte-level restore, and save a
checksummed report. It never calls `upload`, `delete`, `detach`,
`restore`, `redeploy`, `restart`, or `accept-deploy`. Remote CLI stdout
and stderr are suppressed; it never prints private files, paths or tokens.
If anything fails, the private directory is retained for operator inspection
and no PASS receipt is published.

The private validator now performs a three-way **local** content comparison:
read the complete downloaded file set before archive creation, compare its
name/size/SHA-256 manifest to the archived content, then re-read the same
file set after the quarantined byte-restored rehearsal. The CLI wrapper previously relied chiefly on the child report's
`local_copy_scans_matched_archive=true`. **Final parent-level receipt gate
(2026-11-11):** *after* the child exits successfully, the capture process
separately reopens the private report with bounded, no-symlink reads,
rejects extra/unknown report keys, and checks the exact expected volume,
deployment, runtime commit, schema,
authority and strictly limited nonclaims. It rereads the archive, validates
all stored checksums and paths, verifies its *current* SHA-256 matches the
child's declared digest and file count, rescans the local copied data against
the archive, and rechecks every isolated restored byte and quarantine marker
before allowing `capture-receipt.json`. It rereads the report and the
quarantined restored tree at the final boundary as well. If Rust audit was requested, the
parent also requires explicit positive Rust/source-parity/post-audit fields;
without Rust these fields must state `not_evaluated`. A new receipt field
`post_intake_copy_archive_and_restore_rechecked=true` records the bounded
post-child observation. Tests inject source, archive, recovery-marker and
forged/extended report mutations *after* a real synthetic child PASS: the parent must BLOCK
without publishing a receipt.

This closes a **local post-intake-to-receipt gap**. The parent reuses the
versioned validator's parsing and byte-verification rules, so it is another
temporal observation rather than cryptographically independent validation.
It says **nothing conclusive** about whether the original live Railway
volume had simultaneous writes during the earlier download or whether the
copied bytes are the most recent bytes.

The terminal PASS is
`PRIVATE_CLI_COPY_AND_STRUCTURAL_REHEARSAL_PASS`. The
`capture-receipt.json` explicitly records:

- the CLI's **selected** original volume ID is not separately attested;
- a live directory download does **not** establish consistent atomic capture;
- private copy location does **not** prove separate durable storage;
- no live production restore/restart or provider-independent recovery occurs;
- no elevated authority, Seal, production readiness or decision approval.

The entire folder, including the original copied bytes, `intake-report.json`,
snapshot archive, quarantine restore and capture receipt is **sensitive
plaintext**. Keep it secure and private; delete only under a separately
reviewed data-retention decision.

## What this implementation actually proved

The no-secret CI job
`.github/workflows/stage-d-private-volume-intake.yml` runs private-intake
and capture regression tests, including eight post-child tamper/forgery
scenarios with a **fake local Railway CLI**. It proves the command target cannot drift, plan
mode performs nothing, an absent token fails before a copy, unexpected files,
symlinks and download failures block PASS, and a synthetic exported directory
passes an isolated bytes-restored rehearsal. CI uses no Railway login, no
production data and uploads **no capture artifacts**.

## Self-critique and remaining gates

1. **Operational access is still missing.** This connected ChatGPT Railway
   app exposes service/volume metadata but not actual volume-file download
   or provider backup-creation tools; it cannot run an authenticated CLI task
   on a trusted private computer from this chat. The user's budget/device
   constraints remain a barrier to carrying out a private offsite export.
2. **CLI target is not cryptographically authenticated.** Using exact IDs
   avoids accidental selection but is not a signed provider witness.
3. **Snapshot timing is not atomic.** Running NEXUS can mutate data between
   file reads. Even a structural rehearsal PASS does not prove a consistent
   recovery point. Obtain an atomic provider-backed snapshot or a
   controlled write-quiescent capture with independent operator evidence
   *without modifying the only copy first*.
4. **Recovery is not exercised on the production host.** The isolated
   rehearsal compares copied bytes under quarantine, not a restarted server,
   live authenticated client, independent witness or destructive restore.
5. **Volume retention is not free by assumption.** Native Railway backups
   are metered by incremental storage, and CLI transfers may consume
   egress. This workflow does not initiate cost-bearing provider actions.
6. **Still no full external data copy.** The actual Issue #70 recovery gate
   remains OPEN. Do not merge/read this feature as a claim of backup.

The next actual production prerequisite is an owner-authenticated,
point-in-time-consistent, encrypted off-provider data copy and an
independently controlled isolated restore. Nothing in this PR performs that
operation or changes any Railway deployment, server volume or app token.
`A_out <= A_in`.
