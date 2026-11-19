# NEXUS Mobile — guided start UX acceptance

Date: 2026-11-19. Status: **draft code change, not a public rollout**.

## What this changes

The static, offline-only `apps.html` launcher now starts with a single clear choice:
- **Open Studio** (primary): conversation, music, writing, available Studio tools.
- **Open Motion**: storyboards, local previews and supported exports.
- **Check device**: opens the existing compatibility self-check.

The landing page adds English-first text with short Persian hints, descriptive touch targets,
a skip link, visible keyboard focus, an accessible navigation landmark, a help section,
and reduced-motion-respecting styling. Its HTML and CSS are static. There is **no
new JavaScript, network call, login, analytics, installed model, API key, data
migration, entitlement, permission, or export capability**.

## Acceptance and reproduction

Run on the checked-out branch:

```sh
python3 scripts/test-nexus-mobile-local.py
python3 scripts/test-nexus-android-assets.py
python3 scripts/build-studio-static.py --check
```

For native Android behavior, the existing API 35 emulator workflow tests the
actual WebView chooser, links to Studio and Motion, Android Back navigation,
APK install/reinstall, and original strict embedded-asset verification.
The CLI tests also reject modified package assets and unauthorized paths.

Only the *public-code* starter screen changes. Android APK packaging still
replaces the Termux-specific footer in the embedded chooser; this is checked
by the original Android asset test. The Termux ZIP still binds only to
`127.0.0.1`. On devices, screen-reader and OEM hardware testing remains
a future acceptance step. An emulator is not a substitute for a physical phone.

## Explicit limitations

A user-facing landing page does not make offline model inference, voice
generation, rendered 4K video, native microphone recording, full automated
music creation, cloud browsing, or verified project migration available.
The existing Studio and Motion tools retain their previous limits. Reinstalling
a build with a **different signing certificate** is not proven safe; export
and verify personal data before any device migration.

Do not merge/deploy from this stacked draft before exact-head CI, review
and branch-integration approval. No release, production signing key, external
hosting or personal media is in scope. Authority: `A_out <= A_in`.
