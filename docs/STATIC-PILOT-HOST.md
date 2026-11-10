# Pilot 02: Independent, cost-free static web entrypoint

## What was deployed and what remains separate

- Dedicated **Render static site**: https://nexus-offline-pilot.onrender.com/
- Render resource ID: `srv-dbpjvl8n74is73e63rl0`; first static deployment: `dep-dbpjvlon74is73e63sq0`
- First static deploy source commit: `80aad728fa8e278392716f84d7eded7b593371b1`
- Build: `mkdir -p public && cp web/offline-pilot.html public/index.html`.
- Publish path: `public`. Render's `autoDeploy` setting is **off** so unreviewed pushes to main do not silently replace the deployed pilot.
- The site is a public **entrypoint for an offline, in-browser app**, not a connected server product, with no user account or server data persistence.

Only the self-contained, pre-existing HTML is publicly served. In the browser it does **not** POST workspaces, invoke the Rust gateway, call Railway or store workspace state in remote Render storage. Users must explicitly export JSON and hold it in private storage.

The unrelated pre-existing Render Docker service `nexus` and original Railway NEXUS service/volume were **not** changed by this static deployment. Avoid copying actual personal decision files into GitHub, issue comments, CI or public services.

## Independent verification contract

GitHub Actions workflow `.github/workflows/static-pilot-https.yml` runs a five-case pure local observer self-test, then after main-branch merge or on manual dispatch it independently performs a public **GET** request to the exact HTTPS URL. The observer rejects non-200 status, redirects, wrong MIME type, oversized or differing HTML, wrong source SHA-256, or a missing offline/CSP marker. On success it reports `PASS_STATIC_HTTPS_IDENTITY` with the expected and observed SHA-256. Failed GET is **not** a production-app failure; it indicates this specific public static site identity gate did not pass. No token or mutation is performed.

Render `live` status **alone** is not proof of independent HTTPS reachability. A successful exact-byte GET is proof only that the public pilot HTML was available and equal to the source bytes *at the time of observation*. It does not prove that every Android browser handles local files, that exports are retained by users, that the Rust gateway is safe for production, or that Railway's `/data` volume has a recoverable offsite backup.

## Self-critique and restrictions

1. **Not a full NEXUS deployment.** This is a no-account mobile first-touch prototype. Rust server transactions, persistence and authorization are deliberately excluded.
2. **No unattended release pipeline.** Disabling static autoDeploy prevents drift from unreviewed main commits, but requires manual Render deploy when the HTML intentionally changes; the independent hash gate will then signal the mismatch.
3. **User-held files are plaintext.** JSON export is not encrypted or automatically backed up. The interface must not imply data survives reload or that any clinical, financial or personally identifying content is safe to share publicly.
4. **Trial input versus verified evidence.** The source label and a local event log cannot independently attest factual accuracy, source availability or authenticity. No automatic judgment or Seal is issued.
5. **Cost ceiling.** The static-site settings do not request a paid web service. Actual workspace quota, free allowances and billing policies depend on Render account terms; do not promise unlimited free use.

The authenticated pilot on a durable recoverable Rust host remains tracked in Issue #70. Never close that issue from this read-only static-site test alone.
