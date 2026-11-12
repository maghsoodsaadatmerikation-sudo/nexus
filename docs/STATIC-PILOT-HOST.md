# Pilot 02: Independent, cost-free static web entrypoint

## What was deployed and what remains separate

- Dedicated **Render static site**: https://nexus-offline-pilot.onrender.com/
- Render resource ID: `srv-dbpjvl8n74is73e63rl0`; first static deployment: `dep-dbpjvlon74is73e63sq0`
- First static deploy source commit: `80aad728fa8e278392716f84d7eded7b593371b1`
- Build: `mkdir -p public && cp web/offline-pilot.html public/index.html`.
- Publish path: `public`. Render's `autoDeploy` setting is **off** so unreviewed pushes to main do not silently replace the deployed pilot.
- The site is a public **entrypoint for an offline, in-browser app**, not a connected server product, with no user account or server data persistence.

The independently verified public deployment is pinned to Pilot 06 source
commit `24644558cfe96f8f1a725986efbe94e1710032f2`, as last verified
before the Pilot 08 candidate was merged. The **newer main-branch source
may differ from what Render is currently serving** because autoDeploy is OFF.
The static observer in `.github/workflows/static-pilot-https.yml` checks
the pinned deployed revision independently in both PR and main workflows.
It emits a separate boolean indicating whether current source and observed
live bytes match. A PASS for the pinned deployed revision is **not** a
claim that the new source candidate is already live.

Only the self-contained HTML is publicly served. In the browser it does **not** POST workspaces, invoke the Rust gateway, call Railway or store workspace state in remote Render storage. Users must explicitly export JSON and hold it in private storage.

The unrelated pre-existing Render Docker service `nexus` and original Railway NEXUS service/volume were **not** changed by this static deployment. Avoid copying actual personal decision files into GitHub, issue comments, CI or public services.

## Independent verification contract

GitHub Actions workflow `.github/workflows/static-pilot-https.yml` runs a five-case pure local observer self-test, then after main-branch merge or on manual dispatch it independently performs a public **GET** request to the exact HTTPS URL. The observer rejects non-200 status, redirects, wrong MIME type, oversized or differing HTML, wrong source SHA-256, or a missing offline/CSP marker. On success it reports `PASS_STATIC_HTTPS_IDENTITY` with the expected and observed SHA-256. Failed GET is **not** a production-app failure; it indicates this specific public static site identity gate did not pass. No token or mutation is performed.

Render `live` status **alone** is not proof of independent HTTPS reachability. A successful exact-byte GET is proof only that the public pilot HTML was available and equal to the source bytes *at the time of observation*. It does not prove that every Android browser handles local files, that exports are retained by users, that the Rust gateway is safe for production, or that Railway's `/data` volume has a recoverable offsite backup.

## Self-critique and restrictions

1. **Not a full NEXUS deployment.** This is a no-account mobile first-touch prototype. Rust server transactions, persistence and authorization are deliberately excluded.
2. **No unattended release pipeline.** Disabling static autoDeploy prevents drift from unreviewed main commits, but requires manual Render deploy when the HTML intentionally changes; the pinned deployed-reference hash gate will intentionally fail when public bytes change until independently checked and the baseline is deliberately updated.
3. **User-held export privacy depends on the chosen action.** Pilot 06 supports encrypted file exports; its explicitly warned plaintext JSON option is still plaintext. Pilot 08 source adds opt-in encrypted browser-local recovery, but this is **not** a device-independent backup and is not yet claimed deployed. Neither mode is appropriate for entering real sensitive patient/person data into a public/unknown browser.
4. **Trial input versus verified evidence.** The source label and a local event log cannot independently attest factual accuracy, source availability or authenticity. No automatic judgment or Seal is issued.
5. **Cost ceiling.** The static-site settings do not request a paid web service. Actual workspace quota, free allowances and billing policies depend on Render account terms; do not promise unlimited free use.

The authenticated pilot on a durable recoverable Rust host remains tracked in Issue #70. Never close that issue from this read-only static-site test alone.
