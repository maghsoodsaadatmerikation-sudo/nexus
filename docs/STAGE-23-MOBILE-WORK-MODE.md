# Stage 23 — no-budget, installable mobile NEXUS Work Mode

## Scope

Stage 22 proved that a private, encrypted Work Mode can run as one HTML file.
Stage 23 turns the same human-controlled feature into a four-asset,
integrity-pinned, opt-in Progressive Web App for a dedicated, trusted HTTPS
host. No existing Render or Railway service, secret, original data volume or
billing setting is modified. This is an offline work planner, not a
generative model, live search/chat API, MCP account connection or real server.

Original Railway volume offhost backup and independent isolated restore remain
open in Issue #104. Actual authenticated first-human pilot remains Issue #70.
A green browser test is neither a deployment seal nor an original-volume restore.

## Deliverable

The read-only GitHub Action uploads the generated directory as
nexus-stage23-mobile-pwa-site, retained for 30 days. The output includes
index.html, manifest.json, service-worker.js, two previously committed PNG
icons, .nojekyll and nexus-stage23-integrity.json.

Build or reproduce with:

~~~bash
python3 scripts/test-mobile-work-pwa.py
python3 scripts/build-mobile-work-pwa.py --out build/stage23-mobile
python3 scripts/build-mobile-work-pwa.py --out build/stage23-mobile --check
node --check scripts/test-mobile-work-pwa-browser.mjs
node --check build/stage23-mobile/service-worker.js
~~~

The HTML is based on the previously validated Stage 22 network-disabled
Work Mode. It retains the existing local project/task/notes/file editor,
English/Persian UI and optional AES-256-GCM archive, and uses a distinct
IndexedDB database name for this PWA to avoid silent cross-edition overwrites.
It does not automatically send chat, user files, history or credentials.
Private projects are never placed into a service worker's CacheStorage.

The app keeps connect-src none. A user must click Prepare offline before
any Service Worker registration. The worker pins SHA-256, exact lengths and
types for ONLY four public files: HTML, manifest and two icons. It refuses
redirects, altered files, unreviewed paths, queries and non-GET requests.
Only its own cache namespace is removed on explicit user confirmation.
Existing user browser archives and downloaded encrypted files are not
intentionally deleted when an offline shell is removed.

## Mobile user flow after independently verified HTTPS publishing

1. Open the reviewed, trusted dedicated HTTPS site. Merely finding a live
   website does not prove its bytes match the reviewed development candidate.
2. Select Prepare offline / آماده‌سازی آفلاین. If an asset fails validation,
   the worker refuses the install rather than accepting unknown code.
3. Use the browser menu Install app / Add to Home Screen. Depending on Android
   and browser support, this may be a native-like PWA or only a shortcut.
4. Create a project with tasks and review criteria. Changes require explicit
   human evidence; machine notes cannot complete tasks.
5. Create an encrypted archive with a private passphrase, explicitly Save,
   download the encrypted archive, and keep it outside the browser.
6. Personally test airplane-mode reopening and project unlocking on the
   real device. Browser-origin changes, data clearing and storage eviction
   can destroy locally saved projects.
7. Remove offline shell only when desired. This removes the reviewed
   application cache and worker registration, not your archived projects.

For privacy, use a dedicated trusted HTTPS origin. A compromised same-origin
script or device can still access decrypted in-memory content; AES-GCM does not
prevent active browser compromise. Forgotten passphrases cannot be recovered.
Static hosting does not provide backend account sync, multiuser controls or
off-device custody.

## Free publication and unverified boundaries

GitHub Pages supports public repositories on GitHub Free:
https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site
But this repository's Pages publication source and current account eligibility
are not verified. Its Settings → Pages source must be deliberately configured.
The Stage 23 Action has only contents:read and does not possess Pages,
Render, Railway or OIDC deployment privileges. It produces a ready-to-host
candidate, not a live URL. The real published domain, HTTPS MIME types, hashes,
Service Worker scope and owner Android device require independent witnessing.

Synthetic desktop Chromium acceptance covers a narrow root path and a wide
nested path, explicit install, tampered online response rejection, actual CDP
offline mode, encrypted local resume and controlled cache removal. That is
NOT a physical Android test, a public-host witness, a production restore,
a new paid hosting claim, or an authority Seal.

Constitutional boundary: A_out <= A_in; final judgment remains human.
