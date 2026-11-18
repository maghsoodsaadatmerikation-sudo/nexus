# NEXUS Mobile v1.1 — opt-in offline Motion PWA

**2026-11-18 — staged candidate; not merged or deployed.**

## Why this step matters

The previous NEXUS Android-local ZIP successfully launched Studio and Motion
from the same private loopback Python server. Its Studio PWA had an explicitly
prepared offline copy, but Motion still depended on that server for every
reload. The new scoped public-code worker enables an offline **Motion
editor shell** after initial preparation on a service-worker-compatible
browser.

This is a practical PWA enhancement, not an Android APK and not a video
inference engine.

## Android walkthrough

Use the ZIP from the exact source commit's **successful** GitHub Actions
run, extract in trusted Termux and start the same local server:

```sh
pkg install python unzip
cd ~
unzip /path/to/nexus-mobile-local.zip
cd nexus-mobile-local
python3 run-nexus.py
```

Open `http://127.0.0.1:8765/motion/`, then:

1. Tap **Prepare Motion offline / آماده‌سازی آفلاین**. It must confirm the
   public files have been cached. This is **explicit opt-in**.
2. In a supported Android browser, use its menu **Install app** or
   **Add to Home screen**. Whether installation is offered is controlled
   by the browser and Android implementation.
3. Export any private project as JSON/ZIP and preserve it independently;
   imported user photos, soundtrack and original videos are **not cached**.
4. For a real offline check, stop the Termux Python process and reopen
   Motion from its home-screen icon or the original localhost URL. The
   verified *public editor shell* can be served by its service worker
   without the Python HTTP listener. This works only after a complete
   install and only when browser service-worker storage survives.
5. To remove the offline copy, while the app is open tap
   **Remove offline copy / حذف نسخه آفلاین**. This clears only the Motion
   worker and its `nexus-motion-shell-v1-` public code cache.

**The original Studio remains at** `http://127.0.0.1:8765/`. Studio's
own opt-in worker and encrypted browser storage are intentionally unchanged.
Both apps share the same origin but use separate service-worker scopes:
root for Studio; `/motion/` for Motion. Removing one public-code
cache does not remove user archives or the other's public-code cache.

## Security and integrity

The output ZIP now adds a Motion-specific PWA manifest, two local icon
copies, the small explicit offline controls and an independently scoped
`motion/offline-worker.js`. Its seven public cache assets are:

- Motion HTML, motion-core.js, motion-ui.js, offline-ui.js
- Motion manifest.json and two public NEXUS icon PNGs

The worker verifies **exact byte lengths, SHA-256 and MIME types** before
caching. Every offline response is independently reverified before being
served. A failed install/refresh never claims cached readiness. The
package's Python startup guard verifies the worker/manifest/icons as well
as the original Studio ZIP assets *before listening*. The server refuses
unlisted or private paths and all HTTP writes.

The worker only intercepts `/motion/` shell navigations and the specified
static public URLs; it does not intercept, retain, fetch, alter or upload
user-generated videos, media, API keys, chat history or project files.
The Motion HTML retains `connect-src 'none'` and declares a scoped
same-origin worker policy. Browser providers and storage are still
subject to the device and OS security boundaries. Built-in manifest
and archive hashes are not independent source signatures.

## Actual tests and scope

`scripts/test-nexus-mobile-local.py` exercises the generated public ZIP,
asset tamper denial, source hash, local GET/HEAD serving, media MIME types,
refusal of query/private paths and writes, plus fail-closed behavior when
either the Studio HTML or a Motion worker/asset is changed.

`scripts/test-nexus-mobile-offline-browser.mjs` operates on the **same
extracted ZIP** in a real private Chromium instance. It loads Motion,
checks no automatic worker registration, clicks Prepare, verifies exactly
seven public cache entries, **kills the actual Python loopback server**,
reopens the Motion editor with a successful UI interaction, and tests
explicit removal of the public Motion cache. It does not claim to have
run on Android hardware. CI uploads an independent browser witness and
the final ZIP SHA-256.

## Remaining engineering work

The browser editor still needs to keep running for live video recording,
and local storage of original media must be managed by the owner. Cloud
video inference, continuous 4K FFmpeg rendering, actual Android thermal
benchmarks and true Android APK packaging are separate unresolved tasks.

This is a stacked draft PR after #296 and its underlying Motion PR chain.
No user production service, Railway Volume, Render site, main branch or
existing project data has been changed. Production authority is unchanged.
