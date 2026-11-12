# Pilot 12 — installable, opt-in, integrity-pinned offline NEXUS

## Goal and exact boundary

Turn the existing **free public static browser pilot** into an installable
mobile-first PWA on the **same Render static service**, without connecting
to or changing the production Rust gateway or original Railway volume.
Android Chrome / supported mobile browsers may install a home-screen app;
others may offer only a website shortcut. No native Android APK is created.

The previous standalone `web/offline-pilot.html` retains its independent
`file://` behavior. Only the trusted HTTPS NEXUS origin (and localhost for
disposable CI) can register the web-only service worker.

## Owner-visible procedure (once deployment is independently proved)

1. Open **https://nexus-offline-pilot.onrender.com/** while online.
2. Press **آماده‌سازی حالت آفلاین**. This opt-in alone registers a scoped
   `/service-worker.js`; it fails rather than caching unknown page bytes.
3. Once the app reports **آماده است**, choose **افزودن به صفحهٔ اصلی**.
   If the browser has no install prompt, use its menu and **نصب برنامه**
   or **افزودن به صفحهٔ اصلی**.
4. Open it again and try airplane mode. The shell should load without
   a live network connection, provided the browser has retained its
   cache. This is a device-specific step: CI does not constitute real
   personal Android-device acceptance.
5. For a durable workspace, separately enable the **opt-in encrypted
   local checkpoint** or make a **password-protected independent file**.
   Before relying on a download, select the actual file and verify its
   recovery using Pilot 11.
6. Press **حذف نسخهٔ آفلاین برنامه** and confirm to unregister the worker
   and remove NEXUS app-shell cache only. Close existing tabs to finish
   detaching the old worker. This never intentionally erases encrypted
   local workspace storage or downloaded files.

## Security architecture

- Static app shell (HTML) only. `public/manifest.webmanifest` and
  exactly two binary PNG icons (192×192 and 512×512) support installation.
  Existing Render build command `mkdir -p public && cp
  web/offline-pilot.html public/index.html` is **unchanged**; committed
  `public/` assets are already present for Render static publishing.
- A user must explicitly click the offline preparation button. There
  is **no** automatic worker registration or hidden app storage.
- The worker accepts only same-origin **GET navigation** for `/` and
  `/index.html`, no query. It does not intercept POST, external origins,
  uploaded files, arbitrary paths or Rust API requests.
- Installation fetches the published HTML, enforces HTTP 200,
  `text/html`, non-redirected same-origin `basic` response and size
  limits, then computes **SHA-256 of the actual response body**.
  It must match the **explicit reviewed HTML source digest** embedded
  in `public/service-worker.js`; a stale CDN response refuses install.
  The app-shell cache contains exactly this immutable HTML.
- On navigation, network-first behavior uses online bytes only if they
  match the same digest; offline fallback re-verifies its exact cache
  bytes. This protects against accidental cross-revision shell mismatch
  and corrupted app code, but does **not** prevent a compromised hosting
  account, device or browser from modifying both code and expected hash.
- Future updates must change worker hash and version atomically with the
  approved HTML. Old cache names are cleaned only upon activation of
  a reviewed new worker. Because Render autoDeploy is disabled,
  merging source alone does **not** publish a new app.
- The existing page CSP keeps `connect-src 'none'` and only adds
  same-origin `worker-src`, `manifest-src`, and `img-src` for required
  app assets. No analytics, external scripts, account or new API.
- The shell cache never contains workspace JSON, password, source
  identifiers, form entries or audit events. Any opted-in user data still
  uses the existing encrypted `localStorage` vault and owner-held files,
  independent of Service Worker CacheStorage. Browser clearing may remove
  either cache; neither is an independently recoverable original Railway
  volume backup.

## Independent synthetic acceptance

`.github/workflows/pilot-12-installable-offline.yml` checks manifest,
PNG dimensions, security policy, exact HTML digest pin and site build.
It then boots disposable **real Chromium** on a localhost static server,
proves the worker is **not registered before consent**, explicitly
registers and checks that exactly one HTML app-shell entry exists, verifies
its SHA-256, disables the browser's network using DevTools, reloads the
actual document while offline, exercises the one-click fictional scenario
(two claims and two alternatives with **no human judgment**), then reenables
the network and explicitly unregisters/deletes **only app cache** while
preserving the open synthetic workspace.

The witness is synthetic: it proves browser app-shell behavior on
a CI loopback origin, **not** a genuine human Android device, offline
operation under all hardware conditions, permanent local data retention,
authenticated Rust production use, recoverable Railway `/data`, access
control, release Seal or an SLA. The separate public observer must also
verify exact deployed HTTPS bytes and public PWA assets after promotion.

## Reversibility and cost guard

The same existing Render static service is used with autoDeploy OFF;
no paid provider resource, new subscription or production database/volume
is created. Previous Render static deploy can be selected via authorized
rollback, and source can be restored to the last verified Pilot 11 commit
`ed13887699b49a8494a3178e426ad9192e14d57e` if public verification
fails. A rollback claim must itself pass exact-byte public identity.

Original Railway `/data` independent backup and clean restore remains
[Issue #104](https://github.com/maghsoodsaadatmerikation-sudo/nexus/issues/104);
the first actual authenticated human Rust pilot remains
[Issue #70](https://github.com/maghsoodsaadatmerikation-sudo/nexus/issues/70).
`A_out <= A_in`.
