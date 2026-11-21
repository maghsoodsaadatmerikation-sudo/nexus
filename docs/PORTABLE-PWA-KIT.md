# Portable Installable NEXUS PWA — subpath-safe offline handoff

Status: **unprivileged GitHub CI engineering artifact; no live deployment**.

This is the next stage beyond the direct-download HTML ZIP in PR #192. That
version works from a local HTML file but cannot become a true browser-installed
service-worker application from `file://` on most browsers. The existing
Render PWA only supports the hostname root (`/`). This kit creates a
**relocatable scoped PWA** deployable under any *trusted HTTPS* directory.

## What the package includes

The deterministic ZIP has exactly seven public files in `nexus/`:

- `index.html`: English-first/Persian offline workshop, adapted from the
  reviewed `web/offline-pilot.html` only for relative paths and cache names.
- `service-worker.js`: modified source-pinned worker that handles only
  same-origin navigation inside **its own directory**; rejects mismatched HTML
  bytes and never stores user data.
- `manifest.json`: installable PWA with `scope` and `start_url` as `./`.
- Two 192/512 PNG app icons.
- `PWA-KIT.json`: exact source revision and per-file SHA-256 checksums,
  with all production and release claims explicitly false.
- `START-HERE.txt`: concise English/Persian setup and safety instructions.

The package must be extracted and its contents served unchanged at a **HTTPS**
origin. For example, upload `nexus/` to a GitHub Pages project directory
where the site is accessible at `https://YOURUSER.github.io/YOURREPO/nexus/`.
GitHub Pages availability/configuration is not assumed, and nothing is
automatically uploaded or published by this change. If the host serves the
assets from a different directory prefix, relative references still work.

On the phone, visit the deployed HTTPS URL, select **Prepare offline mode**,
then use the browser's **Install app** / **Add to Home Screen** menu.
The opt-in worker caches **only the validated HTML shell**, not passwords,
conversations, workspaces, uploads, or other account data. Local encrypted
workspaces require separate opt-in saving or password-protected exports.

## Safety against other apps on the same origin

The worker scope and its app shell entry both use `new URL('./', ...)`
instead of `/`. The cache prefix includes the URL-encoded installation
directory pathname. An installation under `/nexus/` does not delete caches
for a sibling installation under `/other/`. Worker requests are limited to
same-origin GET **navigation** to that directory's base or `index.html`,
without query parameters. It cannot intercept or write API traffic or
other origin paths.

The manifest and browser controls use relative assets. This keeps the
original root Render PWA unchanged, including its separate cache namespace.

## Reproducibility and acceptance

`scripts/build-portable-pwa-kit.py` makes one source-pinned ZIP, verifies
every member and source SHA, then publishes it only if destination is absent.
It does **not** silently rewrite source if expected anchor text changes.

`scripts/test-portable-pwa-kit.py` covers relocation, scope, source binding,
mutation, duplicate entries, incorrect icons, authority injection,
symlink/hardlink input and no-overwrite publication. The dedicated GitHub
Actions workflow builds the archive from the exact candidate revision,
independently verifies it, and starts a local static server at
`http://127.0.0.1:8765/nexus/` (localhost service workers are allowed).
A fresh real Chromium profile must PASS **eight** checks:

1. page loads at `/nexus/`
2. no unconsented service-worker registration
3. only scoped opt-in shell cache exists
4. cached HTML SHA-256 equals exact reviewed adapted source
5. real network-offline reload of the actual document
6. synthetic example works offline without machine judgment
7. no synthetic workspace in application cache
8. explicit unregistration cleans only the scoped app cache

The successful workflow uploads the installable ZIP as a downloadable GitHub
Actions artifact with seven-day retention. It needs no Render/Railway tokens
or new paid resource.

## Operational status / nonclaims

- Android Chrome **hardware** testing and actual system installability still
  require human device confirmation; a desktop headless Chrome test at mobile
  width is not equivalent.
- The static bundle does not include a hosted generative model, a gateway
  session, real web search, or production data synchronization.
- SHA-256 manifests verify bytes against the source checkout; they are not
  independent signatures.
- No service has been deployed or configured. Original Railway `/data`
  recovery, Render auto-deploy control and GitHub strict required checks remain
  separately blocked (#154 and #168).
- No merge to `main`, automatic release, Seal or human authority expansion.

`A_out <= A_in`.
