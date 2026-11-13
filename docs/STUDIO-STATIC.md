# Static mobile Studio

The static package is `public/studio`. It contains the integrated Studio,
a scoped manifest, an integrity-pinned service worker and app icons. Build with
`python3 scripts/build-studio-static.py`, verify with `--check`.

The independent public origin is
https://nexus-studio-merikation.onrender.com/.
Render reported LIVE on 13 November 2026 for service
`srv-dbrjurc9v7es73cqe0v0`, deploy `dep-dbrjurk9v7es73cqe1a0`, source
`ba81a44a8150098c636481ec32922ef7e2d93124`. AutoDeploy is off.
The build command verifies deterministic packaging and publishes only
`public/studio`. Provider status is distinct from the exact HTTPS byte check
and public-origin offline browser witness; their reports are uploaded by
[NEXUS Public Studio Witness](https://github.com/maghsoodsaadatmerikation-sudo/nexus/actions/workflows/studio-static-public.yml).
The existing `nexus-offline-pilot` service is not redeployed by this stage.

## Use on a phone

Open the Studio address in a supported browser. Create a project and a new
conversation. The local reflection guide works without a model provider.
The page explicitly says that it hosts no model; checking the default model
connection makes no API call. A separately configured HTTPS model gateway can
still be used with its transient access token and per-request context review.

Choose **Prepare offline use** to cache the app code. Only this explicit action
registers the worker. You can then use the browser's **Install app** or **Add to
Home screen** menu when supported. This does not install an APK. The package
never silently opens saved private work.

Save your session explicitly with an encryption passphrase and keep an encrypted
portable backup. Offline preparation stores only the public app code; it does
not save unsaved conversation drafts. Browser encryption, passphrase and archive
conflict behavior remain unchanged. A separate origin has a separate browser
archive: this package does not automatically migrate the older workshop or
local-launcher archives. Import only a compatible Studio encrypted backup.

**Remove offline copy** unregisters this worker and deletes its own app-code
cache. It preserves the open session and encrypted browser archives. It does
not erase user data. Closing the last controlled tab completes worker removal.

## Verification and limits

The worker caches exactly the public index page and checks its SHA-256 before
installation and before returning an offline fallback. It intercepts only
same-origin GET navigation to the entry page or index.html, without query
parameters. It never caches model responses, source passages, user uploads,
private history or gateway credentials. Manifest/icons are public deployment
assets, not private records. The local code lab retains its isolated Worker.

`studio-static.yml` checks deterministic packaging, the public observer's
negative fixtures, and real Chromium offline lifecycle with synthetic private
work. `studio-static-public.yml` runs after an explicit main commit marked
`[verify-studio-public]`, a review PR whose title includes that marker, or manual dispatch. It GETs only the fixed public
origin, checks exact HTML/JS/manifest bytes and decoded icon pixels, then uses
a fresh disposable Chromium profile to test actual offline navigation,
encrypted reopen, removal and rejection of a corrupted cached shell. It uploads
both reports. No provider credentials or actual user files are used.

A passing Chromium witness is not a real Android hardware test. Installation,
voice support and browser retention vary by device. This static site provides
no hosted model, user accounts, cross-device sync, server-side execution or
Stage D durable-core attestation. Live web sources and remote models still need
network access. No paid service or model is requested by this static package.
