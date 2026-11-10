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
read-only operation `railway volume files --volume ... download / ...`.
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
in chat. Actual Railway CLI login/permissions and the version-dependent
placement of global flags must first be checked in the private environment.
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
`.github/workflows/stage-d-private-volume-intake.yml` runs the existing
five private-intake fixtures plus eleven new negative/positive tests with a
**fake local Railway CLI**. It proves the command target cannot drift, plan
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
