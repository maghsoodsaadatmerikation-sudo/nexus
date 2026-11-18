# NEXUS Mobile — standalone offline Android APK (experimental debug)

**Date:** 2026-11-19. Source branch: `feature/nexus-android-standalone-debug-apk-2026-11-19`.
This is a source-bound **test APK**, not a Google Play release, a signed
production app, or a claim of Android hardware compatibility.

## Why a native wrapper?

The prior NEXUS Mobile package was a source-verified Studio + Motion ZIP
running on Android via Termux/Python and an optional browser-installed Motion
PWA. That still required an external installer or server for first launch.
This PR adds a small **native Java Android Activity** embedding those same
reviewed public Studio and Motion sources directly in an APK.

The APK:
- Installs as **NEXUS Mobile (Test)** with a launcher icon supplied by Android.
- Opens the Studio/Motion chooser and both applications directly inside an
  isolated Android WebView, without Python, Termux, an HTTP listener, a
  provider API key, Internet or any paid hosting.
- Uses the HTTPS-looking, local-only `appassets.androidplatform.net`
  WebView origin. A native request interceptor serves only exact
  SHA-256-verified embedded files. Every other remote URL, HTTP write,
  unknown path and external navigation is denied.
- Requests **no Android permissions**: no INTERNET, camera, microphone,
  contacts or broad storage access. The chooser for original image/audio
  imports is Android's system file picker, launched only on user action.
- Offers **bounded, user-confirmed local exports**. The signed source-only
  Android bridge captures JavaScript-created Blob downloads in 48 KiB
  chunks, limits each to 96 MiB, writes to app-private temporary storage
  and opens the platform's **Save As / Create Document** picker. The user
  explicitly selects where to save. An incomplete export is discarded.
- Disables cloud backup of private WebView app storage. Existing encrypted
  Studio archive code is unchanged.

## Source provenance and runtime checks

`scripts/build-nexus-android-assets.py` deterministically reads the same
reviewed public Studio + Motion sources as the already-tested phone kit.
It omits standalone Python scripts, manifests not intended for public
browser display, service credentials and all private media. A new catalog
binds every public asset by exact length, SHA-256, MIME and the reviewed
Git commit SHA. The native Activity checks **all of them before opening
the WebView**.

This is a source-integrity contract, not an independently trusted code
signature. APK install integrity relies on Android's APK signing system.

`scripts/test-nexus-android-assets.py` rejects modified embedded files,
extra private material, wrong source SHA, overwriting existing output,
unexpected Android permissions and unsafe native export code.

`.github/workflows/nexus-android-debug-apk.yml` creates the exact
candidate's debug APK with Java 17, Android SDK 35 and Gradle. It checks
the real APK signature with apksigner, checks that no permission appears
in the compiled manifest, and compares SHA-256 of **every embedded file**
against the catalog. A downloadable unsigned-authority **debug-signed**
APK, SHA-256, manifest permission report and receipt are published only
after those checks pass.

## Installation (only after successful matching CI)

1. Open the GitHub Action **NEXUS Android Standalone Test APK — Offline
   Native Wrapper** for the expected PR head commit.
2. Download artifact `nexus-mobile-standalone-debug-apk`.
3. Extract `nexus-mobile-standalone-debug.apk` to the Android device.
4. Choose Install from your device file manager. Android may require
   per-source approval for installing unknown apps.
5. Tap **NEXUS Mobile (Test)** to open the built-in Studio and Motion
   chooser. **Termux is not needed.**
6. Import and export projects using the Android system file pickers.
   For Motion video export, the browser's actual MediaRecorder support
   can still vary. No full FFmpeg backend or large language model is
   embedded in the APK.

### Caution about debug builds

This APK is signed by GitHub Actions' **ephemeral debug keystore**. It is
**not** a durable production signing identity; a later CI build may not
be installable as an update over this one. Preserve user data by exporting
encrypted projects before uninstalling or upgrading. There is no automatic
account sync or version-to-version migration guarantee.

This version has not been tested on a physical Android phone; GitHub CI
proves compilation, manifest permissions, embedded asset identity and
APK signing, **not runtime usability on an actual device**. The test build
may trigger Play Protect's standard sideload checks. Do not publish this
debug-signed APK as a Play Store release.

## Limitations

- Studio contains its local guide and optional on-device model controls.
  The APK ships **no model weights** and has no INTERNET permission.
  Remote model/provider calls, web search and online features will not
  work in this offline build. Claiming ChatGPT parity would be inaccurate.
- Motion supports original procedural animations, local photo import,
  editor preview, JSON/ZIP saves and browser-supported short video
  recording. Continuous 4K FFmpeg or an AI text-to-video model is **not**
  inside the APK; the separate Termux/desktop CLI remains available.
- Android WebView differs from Chrome in Web Audio, MediaRecorder and
  supported codec profiles; device/OS acceptance is still required.
- Existing Studio and Motion Service Workers are **not needed** for this
  native, fully embedded UI. The native wrapper does not promise that
  installing a browser PWA inside WebView works.
- This APK is deliberately single-user/offline and has no hosted identity,
  collaboration, remote background jobs or production rollout authority.
- No existing `main` branch, Railway production volume, Render service,
  SDK key or other pending PR is modified. No automatic deployment,
  merging or publication happens.

## Next acceptance gate

Use an actual Android 10–16 device to test 1) first open, 2) rotating the
screen and resuming, 3) uploading a local WAV/image, 4) saving an original
JSON and video, 5) reopening encrypted Studio archives, 6) memory/resource
limits and 7) offline use in airplane mode. A future release requires a
stable developer-owned signing key, a controlled migration/backups process
and explicit user approval.
