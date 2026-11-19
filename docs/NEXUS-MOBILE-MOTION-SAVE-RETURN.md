# NEXUS Mobile — Motion save-first return path

Date: 2026-11-19. **Stacked draft** on guided mobile starter UX. Not a release.

## Fixed navigation

The standalone Rust-served Motion source remains unchanged. In the Android-local
ZIP and signed debug APK, the Motion header now shows:
- **Back to NEXUS Studio**: existing `/` Studio navigation.
- **All tools / همهٔ ابزارها**: navigates to the verified `/apps.html` launcher.

This prevents the old misleading "NEXUS" link from reopening Studio rather than
returning to the app chooser.

Immediately beneath the Motion header, a visible reminder asks users to
**Download project + media ZIP** from Export before leaving. Motion does **not**
automatically save current storyboard edits, photos or audio. The reminder
is advisory: Android's Back button, browser shutdown or system process death
can still discard changes. This is not an autosave or recovery feature.

## Checks

```sh
python3 scripts/test-nexus-mobile-local.py
python3 scripts/test-nexus-android-assets.py
```

The Android API 35 emulator acceptance test now performs a real sequence:
chooser → Motion → visible All tools link → chooser → Motion → Android Back
→ chooser → Studio, using actual UIAutomator taps, native WebView page-readiness
witnesses, APK installation, and in-place same-signature data-preservation proof.
Only successful exact-head CI can substantiate a pass claim.

The local ZIP still has strict manifest/hash verification and `127.0.0.1`
binding; the APK still has no Internet permission and includes only
allowlisted verified public assets. The new home link requires the local
Termux server for the ZIP when the browser's offline worker is serving Motion
alone. Standalone Motion PWA's offline app code cache does not automatically
make `apps.html` available. No private data is copied, uploaded or tracked.

## Release gate

No main merge, APK publication, production signing or public hosting.
Physical Android hardware, actual export/save on device, screen readers
and changed-certificate upgrade have not been verified by this change.
Authority bound remains `A_out <= A_in`.
