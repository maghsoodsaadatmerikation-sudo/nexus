# Pilot 12 — no-account Android hardware evidence kit

Status: **field kit implemented, Android execution NOT verified**.
Follow-up issue: [#271](https://github.com/maghsoodsaadatmerikation-sudo/nexus/issues/271).
Pre-existing Chromium evidence: merged [#269](https://github.com/maghsoodsaadatmerikation-sudo/nexus/pull/269).

## What this is (and is not)

This kit records a *person's self-report* after exercising the **legacy Pilot 12**
PWA at **https://nexus-offline-pilot.onrender.com/** on an Android phone. It is
not the separately hosted NEXUS Studio. It requires no PC, provider credentials,
new hosting, network analytics or private workspace files.

- [Open/download the one-file phone form](../web/pilot12-android-field-witness.html).
- [Strict offline JSON receipt validator](../scripts/pilot12_android_receipt.py).
- [Negative and baseline checks](../scripts/test_pilot12_android_receipt.py).
- [Synthetic Chromium form-interaction test](../scripts/test-pilot12-android-form-browser.mjs) — exercises local file UI only; **not a phone**.

The source hash shown on the form is a **pinned public CI reference**, not a
digest independently measured on the phone. The form runs in its own document;
it cannot inspect the Service Worker, CacheStorage or real network isolation of
the other PWA tab. A user-selected PASS is not independent proof. The receipt
always reports `independent_hardware_verified: false`,
`device_sha256_measured: false` and `production_release_authorized: false`.

## No-computer phone procedure (English / فارسی)

1. On Android, open the form's GitHub file link above, choose **Download raw
   file** from the file page, and open the downloaded `.html` file from the
   phone's Files app in a browser supporting local HTML. Some browsers may
   show a local-file warning or may not permit local HTML execution; if so,
   leave the report *Not tested* rather than bypassing security settings.
   در گوشی فایل HTML را از GitHub دریافت کرده و به‌صورت محلی باز کنید.
2. In a **separate browser tab** open the exact old public Pilot 12 URL above.
   Do not start with the newer Studio address. Prefer an unused browser
   context; use fictional content only and do not change existing encrypted
   workspace data. آدرس نسخهٔ قدیمی Pilot 12 را باز کنید؛ دادهٔ شخصی وارد نکنید.
3. While **online**, explicitly choose **Prepare offline mode** on the real
   public PWA. Check its displayed ready state and add its shortcut using the
   browser's supported Install/Add to home screen action. If installing is
   unsupported, report *Not tested* or *Fail*; a shortcut by itself does not
   imply offline cache verification.
4. Put the phone in airplane mode **and verify Wi-Fi and cellular data are
   both off**. In a *separate* tab, try an unrelated public internet page
   to confirm external access fails. Do not accept a `navigator.onLine`
   value as independent network proof.
5. Fully close and reopen the NEXUS shortcut offline. A real NEXUS app UI
   should appear instead of a Chrome error page. Run **only the fictional demo**
   and check that claims/alternatives appear without an autonomous human
   judgment. Close and reopen offline a **second** time.
6. **Only if using an isolated disposable profile**: restore internet,
   explicitly remove the offline app copy from the app UI, and check that
   unrelated workspaces or exported files were not deleted. Otherwise leave
   removal tests *Not tested* — do not erase valuable state to complete
   a checklist.
7. Return to the form, choose Pass/Fail/Not tested for each step, check the
   physical-Android and fictional-only attestations only when true, and choose
   **Generate receipt**. Use Copy or Save JSON to retain the report *locally*.
   It is never automatically uploaded. No identifying OS fingerprint, account,
   message, screenshot or workspace content is requested.

## Result and independent acceptance boundary

A complete truthful self-report is labeled
`USER_REPORTED_PASS_UNVERIFIED`. It is **not** hardware acceptance, app-source
attestation, CacheStorage byte proof, or permission to publish to Render,
Railway or an app store.

To inspect a receipt on a system with Python 3.10+:

```bash
python3 scripts/pilot12_android_receipt.py nexus-pilot12-android-self-report.json
```

The validator accepts only known fixed fields/values, rejects duplicate JSON
keys, unrecognized text fields, invalid or forged authority flags, oversized
receipts, broken stage sets and inconsistent outcome claims. It never prints
the user's entered contents. Its maximum output for a complete self-report is
`PENDING_INDEPENDENT_REVIEW`; it never returns independent `PASS`.

Run negative tests with:

```bash
python3 scripts/test_pilot12_android_receipt.py
NEXUS_ANDROID_FORM_CHROME=/path/to/chromium node scripts/test-pilot12-android-form-browser.mjs
```

A **true independent hardware gate** still needs evidence collected or
witnessed separately, by a person authorized to test a real device:
actual physical device and app-origin verification, direct browser/app
reopening while both radios are off, CacheStorage integrity and worker state
(in an authorized device-debug session where available), and safe
non-sensitive observations. If such evidence is unavailable, issue #271
remains open. Test tooling does not authorize accessing private device data.

No public application bytes, React/Studio source, persistent user records,
Render settings, Railway volumes or secrets are modified by this kit.

## Test and threat model

The HTML carries a restrictive CSP (`connect-src 'none'`,
`form-action 'none'`, no external resources) and uses no browser storage,
analytics, XHR or fetch. Receipt export only occurs after the user clicks
Copy/Save; it uses an in-memory Blob. Local file downloads may be handled
differently by Android browser versions, so manual copy of the JSON
textarea is an acceptable fallback.

The validator is intentionally **not** a cryptographic signature or a
trusted hardware attestation. Anyone can edit a JSON file or select PASS on
a desktop; this cannot grant any NEXUS authority. The CI checks its schema
and deliberate fail-closed boundaries, not an imaginary device run.

Human authority remains `A_out <= A_in`.
