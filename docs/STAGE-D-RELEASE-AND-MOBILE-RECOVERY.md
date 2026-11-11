# Stage D — independent release-gate diagnosis and mobile recovery handoff

**Recorded 2026-11-11. NOT a production backup, successful live restore,
authorized release, or first authenticated human pilot.** All source IDs,
statuses and run URLs below are observations from this exact checkpoint,
not a prediction of a future run. `A_out <= A_in`.

## 1. Why the red release gates do not establish seven software regressions

On GitHub `main` commit `04d47bbdbae1c0057cf3a1b9a9139975f1ac6145`
(subject: `fix(stage-d): restrict Railway credentials to authorized volume download (#87)`),
the following *completed* Release Gate runs each failed at their **explicit
release-intent guard**, step 3, rather than at a tested security assertion:

| Gate | Run | Only failed step |
| --- | --- | --- |
| v1.6 | [42989310597](https://github.com/maghsoodsaadatmerikation-sudo/nexus/actions/runs/42989310597) | Fail-closed release intent gate |
| v1.7 | [42989310602](https://github.com/maghsoodsaadatmerikation-sudo/nexus/actions/runs/42989310602) | Fail-closed v1.7 release intent gate |
| v2.1 | [42988799827](https://github.com/maghsoodsaadatmerikation-sudo/nexus/actions/runs/42988799827) | Require explicit exact-candidate release intent |
| v2.2 | [42988828904](https://github.com/maghsoodsaadatmerikation-sudo/nexus/actions/runs/42988828904) | Require explicit exact-candidate release intent |
| v2.3 | [42988828642](https://github.com/maghsoodsaadatmerikation-sudo/nexus/actions/runs/42988828642) | Require explicit exact-candidate release intent |
| v2.4 | [42988843634](https://github.com/maghsoodsaadatmerikation-sudo/nexus/actions/runs/42988843634) | Require explicit exact-candidate release intent |
| v2.5 | [42988845771](https://github.com/maghsoodsaadatmerikation-sudo/nexus/actions/runs/42988845771) | Require explicit exact-candidate release intent |

Each guard requires a **version-specific exact release commit message**.
The observed ordinary security-fix commit is not any of them, so refusing a
new Seal is the desired **fail-closed** behavior. Do not turn these failures
into successes or silence/skip the protective workflows.

The separately checked [NEXUS Verification
#42988772967](https://github.com/maghsoodsaadatmerikation-sudo/nexus/actions/runs/42988772967)
completed SUCCESS (32/32 steps) on this same commit. Engineering success
and release authorization are different claims.

`scripts/triage-release-intent.py` accepts a **sanitized, local metadata
envelope** (schema `nexus.release-intent-triage.v1`) with one exact SHA,
its complete commit message, and exactly seven versioned run records.
Each record must identify the expected workflow, exact same SHA, completed
FAILURE state, and exactly one matching failed release-intent step. The script
reports `EXPECTED_INTENT_REFUSALS_ONLY` only if every rule holds and the
commit is NOT the exact release message for any corresponding gate.
Unknown failures, missing/duplicate runs, different SHA, unfinished results
or a genuine release-intent message **BLOCK** classification.

Exit code zero certifies **only this limited diagnosis**. It does NOT
establish a passing release gate, sufficient deployment evidence, restored
data, current runtime health, or a new Seal. The tool never calls GitHub,
mutates any ref or sends user content; its unit tests use disposable fake
metadata only. It must not be attached to a release-authorizing condition.

## 2. Current true production recovery blocker

Railway metadata inspected on 2026-11-11 showed:

- Project: `2ac7887b-d67a-48be-8a7b-bd54092893ae`.
- Production environment: `56c4bc45-0e62-4aa9-832f-884bb1aa620c`.
- Service: `0032fc74-2c52-475d-b9df-9dca59237d93` (`nexus-stage-d`).
- Original volume: `cc47a350-6c7e-4487-89d9-c4b390f94884`,
  still mounted at `/data`.
- Original deployment: `db2fd959-918e-49d5-b077-1ac74fac9a82`.
- Actual pinned Railway source: `3c0977f4c7fc9fb5e9a78bdb1eeb581cb3cb4959`,
  **not** the latest GitHub `main`.
- Provider service status observed as `SLEEPING`, no staged changes.

This is metadata, **not an inspection of volume contents**. An attached
volume and a successful GitHub CI cannot prove an independently recoverable
backup. [Pilot #70](https://github.com/maghsoodsaadatmerikation-sudo/nexus/issues/70)
must remain OPEN.

The connected Railway interface in this workflow has no file listing or
volume download action, and no authorization to read production secrets.
Do not circumvent that gap with a public API, CI artifact, unencrypted
public transfer, new paid hosting, a restart, or volume detach/restore.

## 3. Mobile-browser-only operator possibility — NOT VERIFIED ENABLED

Railway's [29 May 2026 changelog](https://railway.com/changelog/2026-05-29-cli-volumes)
describes an **in-browser service Console with live file browser**, where
an eligible operator can download files. It was introduced as a Priority
Boarding feature. An account read-only check on 2026-11-11 showed
`priorityBoarding=false` and no exposed enabled Console-specific flag.
Therefore this option is **conditional**, not a proven feature accessible
to this account. Do not switch the entire account into experimental
Priority Boarding, which enables other beta features, merely to collect
Stage D evidence.

If the operator *already* has an accessible, authorized **Console** tab
in a mobile browser, the safe, non-destructive handoff is:

1. Sign in privately to the official Railway dashboard; locate the project,
   production environment and exact `nexus-stage-d` service by identity.
2. Open the already available file browser, if present, and inspect `/data`
   *without running shell commands or editing files*. If the browser or
   volume directory cannot be accessed, stop and record **BLOCKED**.
3. If the interface provides safe downloads, save **private copies** of
   every workspace `*.json` record, all `requests/` marker files and
   the possible `.nexus-recovery-required` state. The ability to download
   an entire directory in a mobile browser is **not verified**. A partial
   file selection must NEVER be labeled a full volume backup.
4. Preserve the exact relative paths, a private acquisition timestamp,
   independently computed SHA-256 checksums, original tree/file-count
   evidence and the identity of the selected volume. Store copies in
   access-controlled **encrypted** storage outside Railway. Do not upload
   bytes, IDs, credentials, screenshots of private data or file manifests
   to GitHub Issues, Actions, this chat or public storage.
5. Independently compare a second isolated recovery to the private copy,
   under the quarantine rules in
   [STAGE-D-READONLY-CLI-CAPTURE.md](STAGE-D-READONLY-CLI-CAPTURE.md).
   Only a separately witnessed point-in-time-consistent complete copy and
   successful isolated restore can advance the real recovery gate.

**Self-critique:** A web file browser does not inherently provide a
consistent point-in-time snapshot; sequential downloads can race live
writes. Downloading into a phone alone does not prove encrypted custody
or independent restore. A `SLEEPING` deployment might not offer a Console,
and access or transfer charges can depend on account status. This
document makes no claim that these steps ran or are currently possible.

If the mobile Console path is unavailable, the existing pinned CLI path is
documented in
[STAGE-D-READONLY-CLI-CAPTURE.md](STAGE-D-READONLY-CLI-CAPTURE.md)
and remains **not runnable from this chat's Railway connector**. The CLI
path also lacks atomicity/independent restore proof. Neither path permits
changing the original production mount merely to obtain a backup.

## 4. Acceptance boundary and nonclaims

**Completed in this step:** exact-SHA independent diagnosis of seven
historically red release-intent jobs, safely tested offline triage rules,
and a phone-compatible *conditional* recovery handoff.

**Not completed:** actual operator file access, authoritative contents
inventory, remote provider snapshot, full encrypted off-provider backup,
atomic capture, separate authenticated restore, live human workspace
session, promotion or Seal. No actual provider volume operation or payment
has been made. Keep Issue #70 OPEN until those independent gates pass.
