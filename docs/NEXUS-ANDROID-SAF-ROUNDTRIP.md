# NEXUS Android — real DocumentsUI JSON export/import acceptance

Date: 2026-11-19. Status: **experimental stacked draft**; no release.

## Previously untested behavior

The existing Android API 35 test proved source-bound APK installation, WebView
navigation, and preserving an app-private synthetic file during a same-signature
reinstall. That did **not** prove that a user could export or reimport a file.

This change introduces a **separate, fail-closed real Android SAF test**:
`scripts/test-nexus-android-saf.py`, run after APK installation and the existing
WebView smoke test by `.github/workflows/nexus-android-emulator.yml`.

## Exact Android acceptance steps

1. Launch the actual installed debug APK in a freshly booted Android 35 emulator.
2. Open Motion from the native WebView's visible "Open Motion" link.
3. Tap **Download project JSON** in the actual Motion page.
4. Through the Android `ACTION_CREATE_DOCUMENT` DocumentsUI, explicitly
   select **Downloads** and tap **Save**. Do not bypass Android's file picker.
5. Read the file **from /sdcard/Download**, not from the app-private temporary
   export buffer or a synthetic JS mock. Check that the actual JSON has the
   expected source-controlled schema, 1920×1080 resolution, 30 fps, default
   title and exactly three scenes with durations 4, 5 and 4 seconds.
6. Add a synthetic new scene in the editor, then tap **Load storyboard JSON**;
   select the exported document with Android's real file chooser.
7. Require the editor's accessible confirmation of **Imported storyboard JSON:
   3 scenes**. This feedback is emitted only after the existing storyboard
   validation and `setStory` path succeeds.
8. Publish an acceptance JSON with boolean gate results, export length and
   SHA-256 of **only the public source-controlled default fixture**.

The test refuses hardware other than an Android 35 emulator and uses no
personal content, credentials, private photos or media. The only filesystem
cleanup permitted is the one fixed synthetic output name in the disposable
test emulator. A missing UI action, inaccessible DocumentsUI, incorrect
content, or failed import means **the test fails**. It must not be reported
as passing unless the exact-head workflow completes.

## Still not proven

- Android physical phone OEM compatibility, removable storage/SD cards,
  accessible picker localization, large 96 MiB projects, media ZIP, WAV,
  MP4 and long video exports are *not* tested.
- A successful JSON roundtrip proves neither encrypted autosave persistence
  across OS data wipes nor a safe cross-certificate APK upgrade.
- Default storyboard JSON is public, unencrypted test data; this workflow
  does not decrypt or inspect a real user's encrypted draft.
- There is no cloud deployment, app-store publication, new Android permission,
  model provider or paid resource.

Integration remains **stacked draft** on PR #302; do not merge to main or
publish an APK before exact-head CI and human review. Authority invariant:
`A_out <= A_in`.
