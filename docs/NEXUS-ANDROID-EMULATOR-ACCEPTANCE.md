# NEXUS Native Android — first real emulator runtime and safe-reinstall gate

**Date:** November 19, 2026. **Status:** source-only draft until successful
exact-head CI. This is not a physical-phone certification or a production release.

## Goal

The previous APK PR #298 proved successful Gradle compilation, Android debug
APK signature, absence of network/storage permissions and exact digest matching
of 24 embedded public assets. Compiling a WebView wrapper does not prove that
Studio or Motion can actually be opened on Android.

This follow-up adds a **booted Android API 35 emulator test** in
`.github/workflows/nexus-android-emulator.yml` and an independent
`scripts/test-nexus-android-emulator.py` witness using real `adb` and
Android's `uiautomator` accessibility tree. It builds APK assets from the
reviewed head commit, compiles and signs a debug APK, launches a public Android
system image with KVM acceleration, installs the APK and starts its native
Activity.

## Acceptance checks

- Android's package manager accepts the actual debug APK and confirms the
  installed package; APK still requests **no Android permissions**.
- A **debug-build-only** native JavaScript witness confirms the chooser's DOM
  actually loaded, rather than trusting `am start` alone. Its only log
  content is the static reviewed page path and a true/false readiness result,
  never user messages, image files or project data.
- The test uses the native UI hierarchy to click **Open Motion** and
  **Open Studio** in the real WebView, and confirms both page scripts and
  their corresponding elements loaded. It also checks Android's Back action.
- An actual `adb exec-out screencap` of the synthetic Studio screen is
  validated as a PNG. No private user content is involved.
- A synthetic 64-byte sentinel is created in the app-private `files/`
  directory, the app is force-stopped, and the **same exact APK with the
  same debug signing key** is installed again with `adb install -r`.
  The bytes must remain identical. The relaunched native UI must still work.
- No main-thread fatal Android exception is accepted. A structured JSON
  result is produced **only after** passing these checks.

The source-pinned APK, independent SHA-256, JSON report, permission report
and synthetic emulator screen may be retained as CI artifacts, but only on
a successful test run. No user project is read or transferred.

## What this still does not prove

- **Physical Android phone use is untested.** Android emulators differ from
  phone OEM variants, hardware encoders, microphone/camera availability,
  thermal throttling, storage policy, WebView versions and memory.
- The test does **not** run a real MediaRecorder video recording, Android
  file picker, encrypted Studio archive migration or actual video rendering.
  Those are separate future device acceptance gates.
- Installing the **same signed APK** with `adb install -r` preserving an
  app-private synthetic file is NOT proof that a newly signed debug APK
  from a different GitHub run can update an old debug build. The prior CI
  uses an ephemeral debug signing key. Android normally rejects in-place
  update if the signing certificate differs. **Never uninstall an existing
  NEXUS build containing user data solely to install this test APK.**
  Export and independently verify your encrypted archives before any
  controlled migration.
- This test has no developer-owned production key and does not create one.
  A durable signed update channel needs explicit owner-controlled key
  provisioning, secure backups and version/data migration acceptance.
- A public deployment, a production Android release and a trained
  generative text-to-video model are not provided.

## Reproduce (trusted development machine)

Use Android SDK 35 / build tools, Java 17, Gradle 8.10.2 and an x86_64
Android 35 emulator with KVM. Build source-pinned assets, then:

```sh
cd mobile/android
gradle --no-daemon :app:assembleDebug
cd ../..
python3 scripts/test-nexus-android-emulator.py \
  mobile/android/app/build/outputs/apk/debug/app-debug.apk \
  --report /tmp/nexus-android-emulator-report.json
```

The test refuses to claim success without a booted API 35 emulator. Do not
run with personal accounts or private user files. CI's permission scope is
read-only GitHub contents; no Railway/Render, signing keys, deployments,
source branch merges or production data are modified.

Authority invariant: `A_out <= A_in`.
