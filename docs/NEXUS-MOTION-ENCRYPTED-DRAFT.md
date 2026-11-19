# NEXUS Motion — opt-in encrypted storyboard checkpoints

Date: 2026-11-19. Draft integration only. No production release or migration.

## User experience

Motion's local video editor now offers **Enable encrypted autosave**,
**Restore & resume autosave**, **Pause encrypted autosave**, and **Delete
encrypted draft**. It is strictly opt-in: before choosing Enable, no draft is
written to persistent storage. Creation requires a 12–128 character passphrase
entered twice, and the passphrase fields are cleared after each operation.

After Enable, each valid storyboard edit triggers a debounced (750 ms)
checkpoint; the very first checkpoint is saved immediately. The saved file
is **AES-256-GCM ciphertext** with fresh 12-byte random IV each write, under
a PBKDF2-HMAC-SHA-256 derived key (240,000 iterations, 16-byte random salt).
Only the key in page memory exists during a live tab session. Reloading the
page requires the passphrase to decrypt before restoring. A malformed
checkpoint, incorrect password, unsupported schema, or invalid storyboard
fails closed. No secret key or plaintext is persisted.

Persistent browser `localStorage` contains **at most one ciphertext
checkpoint**, not a log or version history. The storage key is
`nexus.motion.encrypted.storyboard.v1`. There is no network request, external
API, telemetry, sharing, remote sync, auto-open, or credential collection.

## Limits and safety

This saves **only JSON storyboard metadata**, including image/audio filenames
referenced by the storyboard, **never original photo, audio, video or export
bytes**. Restoring an encrypted JSON project does not restore referenced
media; the user must reimport originals and export the complete
**project + media ZIP** themselves. Pausing autosave may leave an older
checkpoint. Closing immediately after a change can lose the newest edit.

Password recovery, cross-browser transfer, cross-origin recovery, browser
data wipe, Android app uninstall, changed signing certificate, corrupted
storage and encrypted archive migration are **not solved**. AES-GCM protects
the checkpoint at rest in the browser's local storage; it does not defend
against malware or scripts already running in the same trusted origin,
a compromised device, or password disclosure. No production-grade
resilience or disaster recovery is claimed.

## Verification gates

- `python3 scripts/test-nexus-mobile-local.py`
- `python3 scripts/test-nexus-android-assets.py`
- `node scripts/test-nexus-mobile-offline-browser.mjs` with the actual
  ZIP extracted and a real headless Chromium browser, via the existing
  GitHub workflow. The test checks no storage before consent, ciphertext
  not containing plaintext, debounced edit, wrong password rejection,
  successful reload recovery, recovery **after stopping the actual local
  server** under the opt-in offline worker, and explicit deletion without
  resaving.
- Android API 35 emulator's debug-only WebView witness now also requires
  `crypto.subtle.encrypt` and visible draft controls. Actual passphrase
  entry / on-device export and physical phone acceptance remain untested.

No main merge, public deployment, signing authority, model weights, external
hosting, or private media is changed. Release remains held pending
all exact-head checks and integration review; `A_out <= A_in`.
