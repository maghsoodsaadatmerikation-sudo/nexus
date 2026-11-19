# Studio private tool lifecycle v1 — November 19, 2026

## Problem

The Studio app's archive lock and erase paths cleared the project-scoped
research, data, astrology and task tools, but **did not call the local Music
Lab and Orchestra Lab cleanup interfaces**. This matters because the Orchestra
UI can retain an unencrypted, user-selected original vocal WAV in tab memory,
alongside Blob playback URLs and derived audio. The browser archive does not
contain these bytes, so encrypting or locking that archive alone does not
clear the separate tool state.

## Implemented contract

`web/studio-app.js` now declares the versioned, immutable
`nexus.studio.tool-lifecycle.v1` registry with three phases:

- **cancel**: stop stale workspace research/data/astrology operations without
  erasing their working documents;
- **project**: clear project-scoped tasks, data, astrology and research;
- **private**: unload an optional device model and clear all project-scoped
  tools **plus** local Music and Orchestra transient state.

The `NexusStudioUI` interface is frozen and advertises
`nexus.studio.ui.v1` and the lifecycle version. Each tool is invoked
independently: a failure in one cleanup does not skip the remaining tools.
If any supported tool cleanup fails on lock/erase, the app hard-reloads after
clearing its workspace state, so stale tool closures are discarded rather than
silently presented as cleared. Optional `NexusDevice` is skipped when absent.

Project switching intentionally retains independent, unsaved Music and Orchestra
drafts. These drafts **are** cleared when locking or erasing the archive.
This is a scoped tab-memory cleanup contract, not deletion of already-exported
files, system-level caches, downloaded model weights, or copies outside Studio.

## Source and release integrity

The source, standalone bundle and public static HTML were updated together.
The offline service worker's expected SHA-256 and deterministic cache identity
were regenerated from the new public HTML. Static build `--check` and the
immutable source-bound release candidate continue to enforce exact assets.

The new real-Chromium regression
`scripts/test-studio-private-lifecycle-browser.py` uses synthetic locally
generated WAV data and checks:

1. versioned, frozen Studio interface;
2. local Music and Orchestra score creation, plus original vocal import;
3. lock revoking both tool scores, dry vocal, audio URLs and selected file;
4. archive unlock, creation of new transient tool state, then erase revoking it;
5. zero network calls during synthetic test execution.

The regression runs in `.github/workflows/studio.yml`.
This is not proof of a production deployment, general model reliability or
permanent erasure of data already copied outside the browser.
