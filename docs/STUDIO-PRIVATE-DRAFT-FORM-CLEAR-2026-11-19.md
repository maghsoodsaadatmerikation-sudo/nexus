# Studio private form reset and consent coverage — 2026-11-19

## Problem

The Studio private lifecycle now correctly releases score/WAV/voice buffers on
archive lock or erase. Yet Music Lab and Orchestra Lab kept user-entered titles,
arrangement seeds, prompts, mix settings and other form selections in the DOM
after locking an encrypted archive. This could expose an otherwise private
music idea when a shared device remains on the Studio tab.

Furthermore, an *uncomposed* music title or unparsed orchestra prompt was
not counted as unsaved local media; clicking Lock & clear could discard it
without the already implemented consent dialog.

## Implementation

Both Music Lab and Orchestra Lab capture their shipped input/select/textarea
**defaults** once at initialization, after the Music default values are set.
They never snapshot user input as a separate retained copy.

- `hasTransientWork()` is true if the user changed any form field from its
  shipped baseline, even if no score or WAV has been generated. Existing
  score, audio, active render, voice and pending import checks remain.
- On the already confirmed privacy lock/erase lifecycle, `clear()` now
  resets all tool form fields to shipped defaults and clears in-tab
  results, render/mix state, playback Blob URLs and private dry vocal
  bytes. It also cancels stale import/render completions through the
  existing generation/epoch fences.
- On declined lock, no tool cleanup runs and user drafts remain
  unchanged. A prompt-only draft also triggers the existing tab-exit
  warning.
- Routine project switching still preserves independent local music
  drafts; it does not call either tool's private reset.
- Only the browser tab state is affected. The release does **not**
  claim memory zeroization, erase externally exported WAVs or provide
  autosave of compositions.

## Verification

A disposable real-Chromium regression
`scripts/test-studio-private-draft-forms-browser.py` covers:

1. pristine defaults causing no unsaved-work warning;
2. an uncomposed custom title, seeds, tonal mode and edited prompt/mix
   settings causing a warning;
3. declined lock preserving the original drafts and accepted lock
   clearing them;
4. combined score + prompt drafts and their cleanup;
5. encrypted archive erase clearing both tool forms;
6. no provider/network requests for these local flows.

The regression is included in `.github/workflows/studio.yml` along with
the previous audio-only, stale vocal read and privacy lifecycle tests.
The deterministic standalone/public HTML and SHA/size-bound offline
service worker are regenerated from the same reviewed sources.
