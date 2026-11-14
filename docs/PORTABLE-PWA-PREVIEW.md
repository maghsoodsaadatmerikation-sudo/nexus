# NEXUS isolated public PWA preview — source-only release lane

This is a non-production static preview of the seven-file, opt-in
installable NEXUS mobile web app from PR #193, with an independent
minimal root landing page. No authenticated NEXUS Rust gateway is served.

## Source, hosting and scope

The candidate branch `deploy/isolated-portable-pwa-preview-20261114`
includes the prior offline and portable-PWA candidates. The only build
command needed on the static host is:

```bash
python3 scripts/prepare-portable-pwa-preview.py build preview-site
```

Set the static publish directory to `preview-site`. The public page
is then at the static site's root `/` and the installable application
at `/nexus/`, retaining a relative `./` service worker, manifest,
start_url, and cache namespace. The build executes no network calls,
does not read any environment secret, and refuses an existing output
directory rather than overwriting files.

The resulting publication contains only **eight public files**:
`index.html` (landing page) plus the seven verified PWA files under
`nexus/`. The source revision and per-file SHA-256 digests appear
in `nexus/PWA-KIT.json`. This manifest is not a digital signature.

The independent Render static service, if actually created, **must**
have `autoDeploy:no`, `autoDeployTrigger:off`, the exact candidate
branch, and never point to `main`. Creation of a new service is
distinct from merging or deploying the legacy Render NEXUS service.

## Two-stage acceptance

Stage 1: the unprivileged GitHub Actions workflow tests source
structure and 14 adversarial build fixtures, rebuilds and checks
all eight static assets, and opens the nested PWA under a disposable
local HTTP origin in real Chromium. It tests explicit opt-in, only
public shell in cache, true network-offline navigation, a synthetic
non-authoritative decision example and scoped uninstall.

Stage 2: only after an isolated static host exists, a separate public
read-only witness should retrieve each known public URL, compare
checksums and mime types (decoded PNG pixels where CDN compression
may differ), and rerun Chromium against the **actual HTTPS origin**.
A deployed provider status alone is not proof of public asset identity
or the offline experience.

## Use on Android

Visit the dedicated **HTTPS** preview URL ending in `/nexus/`.
Select **Prepare offline mode**, then use the browser menu **Install
app** or **Add to Home Screen**. Open again after switching off
Wi-Fi/mobile data. English and Persian are available. Do not enter
irrecoverable personal information into a demo: export your work as a
separately protected file, verify reopening it, and keep the passphrase.

The preview does not sync across devices and does not provide hosted
AI, public search, accounts, authenticated requests, or durable
off-host personal backups. Tests on desktop Chromium at mobile width
are not hardware Android acceptance.

## Security and outstanding production holds

Render static hosting is described as free in Render's public docs,
subject to included bandwidth and build-minute limits. The preview
service should never use production credentials or private volumes.
If quotas or plan requirements change, stop before a paid upgrade.
Existing Render services and their deployed revisions are untouched.

This isolated host does not resolve the real gateway's Render
auto-deployment risk, GitHub required-check strictness or the missing
offsite encrypted actual Railway `/data` restore witness
(#154, #168). It is a prototype handoff, not a production release
or a Seal, and never grants machine or merge authority.
