# NEXUS Studio storage transparency center — 2026-11-19

## Why this change exists

Studio's previous single `#retention` label used the archive dirty bit
alone. It could display "saved" when an unsent chat message, uncommitted
document edit or unsaved Music/Orchestra score remained in the tab. In
addition, different code paths independently calculated whether locking
or exiting could lose data.

## User-visible behavior

A compact, expandable **Storage & unsaved work** section is visible near
the top of standalone and installable Studio, in English or Persian (RTL).
It distinguishes four specific categories:

1. **Applied projects and conversations:** tab-only/locked; locally applied
   but not yet saved; or up-to-date encrypted browser archive.
2. **Unsent chat:** message text, temporary per-turn attachments, selected
   document excerpt, and prepared-but-unsubmitted model request.
3. **Writing and preferences:** unapplied writing canvas, project
   preferences or astrology profile drafts.
4. **Music and original vocals:** local Music Lab/Orchestra Lab draft forms,
   scores, output WAV and pending original-voice imports; these are NOT
   included in the encrypted archive and must be exported separately.

Every status is a fixed localized description. No chat text, prompt,
passphrase, voice content, filename, source excerpt or media bytes are
inserted into the visible status or returned by the new API.

## Single risk source and API

`NexusStudioUI.storageStatus()` returns a freshly computed, immutable
`nexus.studio.storage-status.v1` snapshot with:
- `archive`: `tab-only`, `applied-unsaved`, or `encrypted-current`
- `appliedUnsaved`: boolean
- `drafts.chat/writing/preferences/music/orchestra`: booleans
- `lossRisk`: the union of applied unsaved data and in-tab drafts

The same `lossRisk` drives the archive lock confirmation, the
`beforeunload` warning, and the status bar; it replaces several
inconsistent copies of the loss guard. Existing `uiStatus()` properties
remain available for consumers, with a new `lossRisk` boolean.

The status refreshes on normal DOM input/change, Studio controls updates
(including successful/failed save), and explicit Music/Orchestra
`nexus-studio-media-state` events when async render, import or reset
operations change transient media state. No timer or polling service,
new network dependency, or data retention is introduced.

## Limits and verification

The status reports what the *current browser tab* knows, not whether the
user has created a backup on another device. It cannot prevent browser
crashes, erase exported files, guarantee physical memory zeroization or
claim permanent secure deletion.

`scripts/test-studio-storage-status-browser.py` runs in disposable
narrow/wide Chromium. It verifies truthful status before and after
creating/saving an encrypted vault, unsent chat, unapplied canvas,
form-only music and orchestra drafts, declined/approved lock, visibility
without content leaks, Persian RTL and mobile no-overflow, and zero
provider calls.

The deterministic standalone bundle and installable public shell, plus
the source-bound offline worker SHA/size/cache identity, were regenerated
from the reviewed source. The CI suite continues to enforce exact bytes
and browser lifecycle constraints.

This PR is review-only and does not authorize deployment.
