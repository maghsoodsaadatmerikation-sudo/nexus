# Stage 26 — Genuine Android-emulator acceptance before any owner-device claim

## Motivation and actual scope

Stage 25 generated an Android 8+ installable, offline signed preview APK from
the reviewed local NEXUS Work Mode. Its Java source compiled and APK signature
and permissions were audited, but it was **never executed by Android**.

Stage 26 adds an independent, test-only Android **API 35 emulator** gate.
It does not ask the user for a computer, pay for a host, run a public service,
access Railway /data, request backend authorization or change production main.

## What is verified

This stage runs an Android SDK emulator in the GitHub PR verifier, installed
from the official Android 35 Google APIs x86_64 system image (KVM acceleration
required). Unlike Chrome desktop emulation, the target is the actual Android
platform WebView and Android IPC code. The existing Stage25 app APK is built
and audited again. A SECOND emulator-only copy is re-signed with a fresh
temporary certificate, as is the independent platform-instrumentation APK.
Every APK ZIP entry **other than signatures** must be byte-identical to the
original Stage25 artifact. The two emulator APK certificates must match.

The on-emulator test invokes native Activity/WebView and confirms, using
synthetic data only:

- The expected review-pinned local HTML opens under the app-owned
  https://appassets.androidplatform.net/nexus/index.html origin.
- WebView direct file/content access is disabled, and no Service Worker runs.
- The user-review rule rejects marking tasks done without required evidence.
- A synthetic task completed with explicit review can be stored in a
  real WebView IndexedDB as AES-GCM encrypted data; a synthetic encrypted
  backup does not contain the synthetic project marker in plaintext.
- The Android Activity is closed and a new Activity launched, after which
  the encrypted project is decrypted from **persistent** IndexedDB.
- An incorrect archive password is rejected, and a tampered encrypted
  backup cannot overwrite the successfully saved project.
- The Android system ACTION_CREATE_DOCUMENT and ACTION_OPEN_DOCUMENT
  intents are invoked from the native user-mediated export/import bridges.
  The test cancels these pickers; it does **not** claim that actual
  document bytes were written and successfully imported.

All checks run with zero app INTERNET permissions; no provider SDK, token,
network search, plugin or backend account is installed.

## CI and security boundaries

The new stage26-android-emulator.yml runs only on pull requests against
feat/work-mode-20261113, with contents:read and no attestation/write
permissions, secret, production job or Pages/Render integration. It
independently validates source invariants, builds original Stage25 APK,
creates same-signer emulator-only APKs with a fresh throwaway one-day cert,
destroys the signing key before emulator boot, installs only emulator-test
packages, runs Android platform instrumentation and parses the actual
INSTRUMENTATION_RESULT fields fail-closed.

Required public report status:
ANDROID_EMULATOR_SYNTHETIC_ACCEPTANCE_PASS. If KVM is unavailable,
emulator startup fails, WebView does not run, any crypto/check fails, or
the APK signatures differ, the workflow remains failed. Do not substitute
a synthetic unit-test fixture for an Android runtime PASS.

The witness reports test-only steps and SHA digests, not private project
data. No certificate private material is uploaded.

## Limitations and self-critique

Android emulator proof is NOT a physical owner-phone test, a Play Store
release, production signing-certificate custody, a stable update path,
a real external SAF file write/import with readback, real-device memory
survival across system reboot or an external off-host Railway restore.
These must remain separate. A hosted NEXUS server and native AI/chat/search
remain unavailable in the zero-network mobile edition.

If SDK tools or Google system images change, the emulator runner may
require maintenance. Stage 26 intentionally fails rather than inventing
a device proof. Use no actual or irreplaceable user data in the signed
experimental APK. NEXUS authority remains human: A_out <= A_in.
