# Phase 41 — NEXUS Studio on a phone without hosted NEXUS services

**Goal:** provide the current, fully reviewed static NEXUS Studio in a deterministic GitHub Actions ZIP, with a read-only Python HTTP server bound **only to the same phone's `127.0.0.1`**. This offers a concrete no-paid-host path to open Studio on Android using Termux. It does not create a native APK, install or validate a local LLM, change Render or Railway, or grant NEXUS production authority.

## Why a different path from the dormant Stage D server

The repository already has a public static PWA at [NEXUS Studio on Render](https://nexus-studio-merikation.onrender.com/) and a tested opt-in service worker. Existing documentation says the independently deployed public static site used a pinned, older code revision and its automatic deployment was disabled. The newer `main` branch can therefore be ahead of the hosted site. This local ZIP builds from the exact reviewed candidate commit, avoiding a risky backend cutover and any access to the original `/data` Railway Volume.

## Phone workflow

1. Download the **successful exact-main** GitHub Actions artifact from [NEXUS Studio Phone-Local Distribution](https://github.com/maghsoodsaadatmerikation-sudo/nexus/actions/workflows/studio-phone-local.yml). It contains `nexus-studio-phone-local.zip`, a SHA-256 file, and a synthetic real-Chromium witness JSON. The internal manifest only reports its own bytes; independently compare the external CI SHA-256 with the downloaded ZIP.
2. On the phone install a trusted Termux distribution and install Python/unzip using its normal package manager; these public dependencies may require internet once. Extract ZIP under Termux's private `$HOME`, not shared/synced directories.
3. In Termux run:

```sh
pkg install python unzip
cd "$HOME"
unzip /ABSOLUTE/LOCATION/nexus-studio-phone-local.zip
cd nexus-studio-phone-local
python3 run-local.py
```

4. Open **`http://127.0.0.1:8765/` on the same phone**. This loopback origin is treated as potentially trustworthy by major browsers for the service worker; actual browser and Android device behavior can vary. Create a project, use local guide and tools, then save the archive with a passphrase and keep a separately exported encrypted backup. Select **Prepare offline use** to cache the public app shell; the browser may then offer **Add to Home screen**.

5. Do not switch from `127.0.0.1` to `localhost`, HTTPS or a different port when trying to reopen your encrypted browser archive: they are different origins. Stopping Termux can stop the loopback server; offline worker navigation is best effort and is not a substitute for keeping an encrypted portable backup.

## Boundaries and security

- **The ZIP includes only 13 public reviewed static Studio assets** (HTML, service worker, PWA manifest, icons, public on-device-model control scripts and public vendor licenses), plus the public-only Python server, instructions and source-bound manifest. No private files, API tokens, user archives, original Volume data, production keys, large model weights or full codebase.
- The launcher verifies every asset's SHA-256 against the exact source-pinned manifest **before** starting; it serves a strict public-path allowlist and rejects arbitrary paths, queries, POST/PUT/DELETE. It binds only to `127.0.0.1`, never a LAN address, and has no private-data upload route. A private origin means only a device-level/OS boundary, not security against hostile local apps or a compromised phone.
- Studio is not ChatGPT. The local deterministic reflection guide, project/chat history, writing/data analysis, code lab and opt-in encryption are usable without a hosted model. On-device small-model weights are an **additional optional, potentially large download** and actual inference depends on device RAM/browser support. Generative hosted models require a separate configured gateway and provider authorization; a ChatGPT subscription does not imply API access.
- The browser itself may fetch public research sources or an optional model provider when explicitly used. The **Python launcher** makes no such requests. Package contents and public code caches do not include private history; browsers keep encrypted archives at the exact origin only after explicit saving.
- No paid host, Render deploy, Railway wake/restart, source switch, production release or original volume mutation. The old PWA on Render remains separate.

## Reproducible CI and real browser acceptance

`scripts/build-studio-phone-local.py` checks `scripts/build-studio-static.py --check`, strict existing static HTML and service-worker hash, and packages a deterministic archive. `scripts/test-studio-phone-local.py` independently exercises real localhost HTTP requests, no external binding, exact byte responses, blocked arbitrary file/path/POST access, tamper rejection, reproducibility and pre-existing output protection. `scripts/test-studio-static-browser.mjs` accepts `NEXUS_STUDIO_PACKAGE_DIR` only when the operator explicitly chooses a verified **extracted ZIP**; on GitHub CI it executes the existing real Chromium offline/encrypted-history/PWA lifecycle against those extracted bytes, rather than only testing the build tree.

**Not proven:** physical Android/Termux support, real-device model generation, provider availability, unattended background operation, independent production backups/recovery or live Stage D approval. `A_out <= A_in`.
