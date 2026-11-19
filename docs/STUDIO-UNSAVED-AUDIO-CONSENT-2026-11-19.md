# Studio unsaved-media consent and pending-vocal exit guard — 2026-11-19

## Finding

The previous privacy cleanup made archive lock and erase correctly release
temporary Music Lab and Orchestra Lab state. However the archive-lock
confirmation only checked unsaved chat, preferences, writing drafts and
attachments. A user who had composed music or imported a private original
vocal without editing chat could click **Lock & clear** and silently lose
the music score, rendered WAV, reviewed orchestra plan, and local voice
preview.

The browser's beforeunload warning also did not account for these local
media tools. Their data resides in tab memory outside the encrypted vault.

## Implementation

- `NexusMusicUI.hasTransientWork()` reports scores, rendered WAVs and
  in-progress renders.
- `NexusOrchestraUI.hasTransientWork()` reports a parsed plan, score,
  rendered WAV, original dry vocal, mixed WAV, rendering/mixing, and
  pending original-vocal imports.
- The Orchestra importer has a `dryPending` flag tied to the existing
  `dryEpoch` generation. The flag is cleared on explicit private-voice
  removal or final completion of the current import; stale completions
  are not allowed to reactivate it.
- `NexusStudioUI.uiStatus().unsavedLocalMedia` exposes the combined status
  without copying, storing or uploading the private WAV bytes.
- Lock & clear requires existing translated discard confirmation if
  local media exists, and respects a declined choice.
- Beforeunload warns for unsaved local media and previously unguarded
  in-memory chat attachment selections.
- Archive erase already explicitly requests confirmation and retains its
  existing cleanup behavior; project switching continues preserving
  independent local Music and Orchestra drafts as previously documented.

## Regression and constraints

`scripts/test-studio-unsaved-audio-browser.py` exercises a disposable
real Chromium page with locally generated synthetic WAV content. It tests
that Music drafts, reviewed orchestra plans and pending or completed vocal
imports trigger confirmation, declined lock preserves media, accepted lock
clears it, stale import completion cannot repopulate cleared state,
and beforeunload warnings are suppressed after cleanup.

Only a local, per-tab warning is added. This does not prevent loss due to
device crashes or browser termination without beforeunload, and cannot
delete files already exported to storage. The user still needs to export
important music and encrypted workspace backups.

Source JS, standalone HTML, public installable HTML and the source-bound
offline service worker hash/size must remain deterministic.
