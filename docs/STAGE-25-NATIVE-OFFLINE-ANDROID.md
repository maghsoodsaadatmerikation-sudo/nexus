# Stage 25 — executable, entirely offline Android APK test edition

## Why a direct Android APK?

The current repository has an independently reviewed seven-file Work Mode
PWA source branch, but GitHub Pages is **not enabled**. GitHub's own
configure-pages action requires an administrative token other than
GITHUB_TOKEN for auto-enablement. Stage25 therefore avoids a paid host,
long-lived token or laptop by compiling a **standalone installable APK**.

This is **NEXUS Work Mode only**, with human-reviewed tasks, notes, local
file attachment, project dependencies and an opt-in encrypted archive.
There is no network search, model inference, plugins, multi-device sync,
remote server, autonomous operation, delegated judgment or user account.
Its final judgment remains human.

## Architecture

- Package: org.nexus.offline.stage25; app label NEXUS Offline Preview.
- Android API 26+; target 35; no Android permissions, including no Internet,
  camera, microphone, location, contacts, storage or other privileges.
- Single Activity with the platform WebView. Reviewed Stage23 HTML is
  transformed to remove the PWA Service Worker and browser install
  controls. CSP still contains connect-src none, frame-src none and
  form-action none.
- HTTPS-like app-owned asset origin:
  https://appassets.androidplatform.net/nexus/index.html
  WebViewClient explicitly intercepts only the exact local HTML and
  returns 403 for EVERY other request; external navigation is blocked.
  Neither the app nor a third-party dependency has Internet permission.
  All HTML/JavaScript content is bundled in the APK.
- The local IndexedDB archive remains in the compatible Stage23 mobile
  encrypted vault namespace, using AES-256-GCM and a user passphrase.
  Android application backup is disabled (allowBackup=false).
  The database can still be erased by an app uninstall, browser-storage
  eviction or OS reset.
- Android document-open chooser handles optional private file import.
  JavaScript has one narrowly scoped bridge function for exporting a
  bounded blob. The Android ACTION_CREATE_DOCUMENT picker always asks
  the user where to save files. This enables an independent encrypted
  backup download, Markdown export and file export without a shared
  filesystem permission.

## Reproducible build and public evidence

The GitHub Actions job in stage25-android-apk.yml uses a runner-provided
Android SDK, Android API 35, build-tools 35.0.1, Java, aapt2, d8,
zipalign, keytool and apksigner. No Gradle plugins or external libraries
are installed. It creates a disposable RSA test certificate on the runner,
compiles real Java bytecode and resources, packages native classes.dex,
signs an APK, checks the APK signature, checks packaged HTML hashes and
verifies the manifest declares zero Android permissions.

The artifact named nexus-stage25-android-offline-test-apk contains the
installable test APK only. The independent evidence artifact contains
its SHA-256, the **public** signing certificate digest, Android manifest
permission audit and input source digest.

Run local checks with:

    python3 scripts/test-stage25-android-assets.py
    python3 scripts/build-stage25-android-assets.py --out build/stage25-input
    python3 scripts/build-stage25-android-assets.py --out build/stage25-input --check
    bash scripts/build-stage25-apk.sh

## Critical test-build limits

This APK uses a **new short-lived test signing key for each CI build** and
does not ship the signing key. An APK built in a later run cannot update
the same package in place. A failed update or uninstall can erase the
in-app encrypted vault. **Do not put irreplaceable data into this APK.**
Before removing the app, use the encrypted backup export through Android's
document picker, keep the passphrase privately, and independently verify
the exported file. A permanent signing key with secure custody is a
separate production launch gate. Never publish a persistent signing key
in GitHub Actions logs, artifacts or source.

This stage does not install the APK on the actual user's Android device,
and static APK package/signature validation does not prove device-specific
WebView IndexedDB, file picking, dialogs or UI work. The owner must also
verify Android's unknown-app installation prompt and its publisher
fingerprint before using this experimental APK. It is not Google Play
published or an official signed NEXUS stable release.

For a trial on Android, download the verified APK, open it from the file
manager, approve installing from this source only if the OS offers the
choice, and launch NEXUS Offline Preview. Test using fake project data,
a user-approved project save, a test encrypted backup through the
Android system file picker, closing and reopening, and a new test
restore. When the app is replaced or removed, app-local storage may be
lost. The APK makes no external network requests.

The original Railway /data off-host independent backup and isolated
restore remain unresolved (#104), and a live authenticated backend pilot
remains unresolved (#70). APK success is not either of those proofs.

## Self-critique and follow-up gates

This approach removes the public Pages setup block and creates a
downloadable binary without a paid host or PC. It is limited to local
Work Mode; no ChatGPT-equivalent capabilities are implied. It also
introduces code-signing and real-device acceptance risks. Safe production
would require durable secure signing custody, independent Android
device-specific functional tests, update/restore tests and release
provenance without storing signing secrets in public GitHub materials.

The Android WebView's browser runtime remains a trust boundary:
malicious browser bugs or a compromised Android device could expose
unlocked content. The independent encrypted file is a recovery control,
not a guarantee that future builds can be upgraded or that original
server data is restored. Release authority is not granted; A_out <= A_in.
