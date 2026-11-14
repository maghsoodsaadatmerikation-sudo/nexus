# NEXUS on-device readiness — privacy-first pilot acceptance

Status: **user-run compatibility probe**, not a remote device attestation.

## Open on the phone (no computer required)

- Public preview: https://nexus-merikation-pwa-preview.onrender.com/nexus/
- Mobile checker: https://nexus-merikation-pwa-preview.onrender.com/nexus/device-check.html

1. Open NEXUS on your Android phone and choose **Prepare offline mode**.
2. Use the browser's **Install app** / **Add to home screen** menu when it is available.
3. Open the app from the home-screen icon if installation succeeded.
4. Enable airplane mode and confirm that the NEXUS app reopens and runs the **synthetic demo** without a live connection.
5. Return online, open **Device readiness**, and press **Run browser checks**.
6. Select only the statements you actually tested. If you performed
   these actions on physical Android hardware, you may optionally
   select that self-report item.
7. If you want a local JSON report, choose **Download privacy-safe JSON**.
   The file stays with the browser download destination; the site does not
   automatically upload it.

The checker itself is not in the offline Service Worker cache (only the
pinned NEXUS app shell is). Return online before opening the checker. It
does not perform the airplane-mode step for you.

## What is automatically checked

The checker reads only boolean support/status indicators: secure browser
context; Service Worker and CacheStorage availability; WebCrypto; local
file export APIs; active scoped NEXUS worker; SHA-256 of the **cached
public HTML app shell**; and whether the checker is displayed
standalone. The actual shell bytes must equal the reviewed source-bound
digest embedded by the static preview builder.

A false `standalone_display` result is possible if the checker was
opened in an ordinary browser tab even though NEXUS was separately
installed. It is a hint, not evidence of failure to install. The
four human checkboxes are self-attestations, not verified claims.

## Privacy and authority limits

The page performs **no fetch, XHR, Beacon, telemetry, user-agent,
geolocation or permission request**. It does not register or unregister
workers, enable a vault, download personal files, access the existing
workspace, read private browser storage or write to localStorage.
It only accesses cached *public shell* bytes and scoped worker metadata.

Its optional JSON export contains a fixed schema, the public shell
SHA-256 and eight booleans, four explicit owner-affirmed booleans,
and explicit `independent_android_hardware_verification=false`,
`private_information_collected=false`, `sent_to_server=false`,
`production_recovery_verified=false`, `release_authorized=false`,
`authority=none`. No timestamps, URL, device identifiers, IP,
device model, user-agent or workspace content appear in that report.

A browser download may still be stored by the owner's device or synced
by their own backup settings; NEXUS does not control external
device/browser services. Users should decide whether to share any
downloaded report.

## Source and acceptance contracts

- `web/mobile-readiness.html` is the reviewed, single-file HTML source.
- `scripts/prepare-portable-pwa-preview.py` substitutes exactly one
  expected public shell digest and publishes it only as
  `nexus/device-check.html` alongside the seven-file PWA and root
  landing page (nine public files total).
- `scripts/test-portable-pwa-preview.py` rejects modified, removed
  or untrusted diagnostic source and tests no-network/no-permission
  contract.
- `scripts/test-mobile-readiness-browser.py` uses a disposable
  real Chromium profile in narrow mobile dimensions, verifies
  user-triggered checks, explicit manual claims, redacted JSON export,
  Persian UI, and zero network requests. This is **desktop Chromium**
  at mobile dimensions, not physical Android hardware.
- The public GitHub Actions witness independently checks all nine
  deployed HTTPS files and exercises the diagnostic on the public
  domain with a fresh Chrome profile and valid installed public shell.

The separately hosted preview remains `autoDeploy=no`, never
connects to production Rust or private Railway volumes, and has no
authority to Seal or authorize a release. Do not treat success here
as offsite production data recovery, real human usability acceptance
on all Android devices, or deployment approval to `main`.
