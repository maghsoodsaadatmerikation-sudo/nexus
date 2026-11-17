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

5. To inspect your **actual browser** without sending anything to NEXUS, keep
   Termux running and open `http://127.0.0.1:8765/device-check.html` in the
   **same phone browser**. Tap **Run private checks**. The page checks its own
   secure context, local-only origin, the exact source-bound Studio HTML
   and worker SHA-256, service-worker registration, and verified public-code
   cache, without opening any projects or reading local browser storage.
   The result is `PASS`, `NOT_PREPARED`, or `BLOCKED`; when not prepared,
   first use Studio's **Prepare offline use** control and check again.
   **PASS only means code/cache readiness, not a genuine offline reload.**

6. For an independent **owner-reported manual** observation, try reopening
   Studio from its installed icon **after stopping the Termux server** and
   switching off internet connectivity. Record what happened with the first
   optional checkbox *only if it really worked*. For the encrypted archive
   checkbox, use a disposable **entirely synthetic** project; never put actual
   private data into an unverified test. These are personal observations, not
   automated proof. Select **Save JSON locally** (or Copy JSON) only if you
   want the report. It includes **no messages, passwords, filenames, exact
   origin, IP, browser fingerprint, device identifiers, or automatic uploads**.
   No one receives the JSON unless you explicitly choose to share it.

7. Do not switch from `127.0.0.1` to `localhost`, HTTPS or a different port when trying to reopen your encrypted browser archive: they are different origins. Stopping Termux can stop the loopback server; offline worker navigation is best effort and is not a substitute for keeping an encrypted portable backup.

## Boundaries and security

- **The ZIP includes 13 reviewed static Studio assets plus one generated self-check HTML page** (HTML, service worker, PWA manifest, icons, public on-device-model control scripts and public vendor licenses), plus the public-only Python server, instructions and source-bound manifest. The self-check source is separately reviewed and SHA-binds the exact Studio HTML and worker at package time. No private files, API tokens, user archives, original Volume data, production keys, large model weights or full codebase.
- The launcher verifies every asset's SHA-256 against the exact source-pinned manifest **before** starting; it serves a strict public-path allowlist and rejects arbitrary paths, queries, POST/PUT/DELETE. It binds only to `127.0.0.1`, never a LAN address, and has no private-data upload route. A private origin means only a device-level/OS boundary, not security against hostile local apps or a compromised phone.
- Studio is not ChatGPT. The local deterministic reflection guide, project/chat history, writing/data analysis, code lab and opt-in encryption are usable without a hosted model. On-device small-model weights are an **additional optional, potentially large download** and actual inference depends on device RAM/browser support. Generative hosted models require a separate configured gateway and provider authorization; a ChatGPT subscription does not imply API access.
- The browser itself may fetch public research sources or an optional model provider when explicitly used. The **Python launcher** makes no such requests. Package contents and public code caches do not include private history; browsers keep encrypted archives at the exact origin only after explicit saving.
- No paid host, Render deploy, Railway wake/restart, source switch, production release or original volume mutation. The old PWA on Render remains separate.

## Reproducible CI and real browser acceptance

`scripts/build-studio-phone-local.py` checks `scripts/build-studio-static.py --check`, strict existing static HTML and service-worker hash, and packages a deterministic archive. `scripts/test-studio-phone-local.py` independently exercises real localhost HTTP requests, no external binding, exact byte responses, blocked arbitrary file/path/POST access, tamper rejection, reproducibility and pre-existing output protection. `scripts/test-studio-static-browser.mjs` accepts `NEXUS_STUDIO_PACKAGE_DIR` only when the operator explicitly chooses a verified **extracted ZIP**; on GitHub CI it executes the existing real Chromium offline/encrypted-history/PWA lifecycle against those extracted bytes, rather than only testing the build tree.

**Not proven by CI:** physical Android/Termux support, real-device model generation, provider availability, unattended background operation, independent production backups/recovery or live Stage D approval. `A_out <= A_in`.

## Phase 45 self-critique — truthful phone-readiness evidence

The earlier workflow was synthetic: a GitHub runner proved the ZIP's Chromium
behavior, but the actual Android device had no built-in, privacy-preserving
way to report which browser features worked. Phase 45 includes a **locally
served** `device-check.html` page and a no-upload JSON export. A read-only
manifest with exact SHA-256 pins the public page itself and the app/worker
bytes. It is separate from the PWA's own installed code cache and never
stores, deletes, exports, or authenticates a user's encrypted archive.

**Potential false-positive addressed:** Airplane mode *alone* does not
establish offline capability when Termux is still serving localhost. The
instructions explicitly require **stopping the local server** before manually
reopening the installed app. User-checked observations are labelled
`owner_reported` and `actual_android_hardware_independently_verified`
is permanently `false` in generated reports. Browser capability PASS is
not promoted into production recovery, live model generation or offline
acceptance of all devices. If exact public assets are modified or the
local server binds externally, packaging/CI must fail closed.

**Render promotion:** The separate Render Studio remains on its independently
pinned deployment; `main` and downloaded local ZIPs do not update that
public origin. A future authorized public promotion must verify deployed
source digest, CSP, PWA opt-in behavior and independently witnessed real
public offline navigation. No release or Railway volume changes in Phase 45.
