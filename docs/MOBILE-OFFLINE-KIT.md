# NEXUS Portable Offline Mobile Kit — first-user handoff

Status: **synthetic source-only acceptance, not a production release**.

## What a person can actually download

A successful
[NEXUS Portable Offline Mobile Kit](https://github.com/maghsoodsaadatmerikation-sudo/nexus/actions/workflows/mobile-offline-kit.yml)
GitHub Actions run contains a downloadable artifact called
`nexus-offline-mobile-<run-id>`. Sign in to GitHub if prompted, open the run,
and select the artifact in the **Artifacts** section. Extract the outer
GitHub Actions ZIP if necessary; it contains `nexus-offline-mobile.zip`.

Extract that inner ZIP. It contains exactly three public files:
`NEXUS-offline.html`, `START-HERE.txt`, and `MANIFEST.json`.
Open the HTML with a capable browser on Android, desktop or another supported
device. The HTML is copied byte-for-byte from the reviewed
`web/offline-pilot.html`; the file is not an APK or App Store package.
Some Android file managers open HTML as text or restrict local WebCrypto.
If so, use the existing HTTPS
[public pilot](https://nexus-offline-pilot.onrender.com/). Phone installation
is dependent on the browser and is **not** proven by CI.

The interface is English-first with Persian bundled. Try the fictional demo,
then start a new workspace. NEXUS can structure evidence, alternatives and
uncertainty but does not own human judgment. The local guide is not a hosted
generative model. No server login, API key, cloud synchronization or paid
instance is needed.

## Preserve your own work

Work is not automatically backed up to a server or included in this ZIP.
Explicitly export a password-protected copy from the app, keep the password
separately, and use **verify downloaded export** to check the *actual* file.
Consent-based encrypted browser checkpoints are tied to one browser/device
and can be lost if browser data is cleared. Opening an offline file in a new
origin may not share vault state with the existing HTTPS site. Do not put
real personal workspaces into GitHub Actions or this kit.

## Repeatable build and verification

From a full checkout, with Python 3:

```bash
python3 scripts/test-mobile-offline-kit.py
python3 scripts/build-mobile-offline-kit.py build /tmp/nexus-offline-mobile.zip
python3 scripts/build-mobile-offline-kit.py verify /tmp/nexus-offline-mobile.zip
```

The deterministic ZIP uses fixed timestamps, mode 0644 and SHA-256 digests.
The manifest records the exact tested source commit, HTML SHA-256 and size,
and explicitly says `production_verified=false`,
`release_authorized=false` and `authority=none`.
Verification refuses unknown files, duplicates, tampering, symlinks,
corrupt archives, stale content, size violations and source revision mismatch.
The tool publishes only to an absent destination without overwriting it.
SHA-256 establishes byte equality, **not** independent cryptographic signing
or provenance custody.

In PR CI, the unprivileged workflow builds the kit from the exact checked
commit, runs the negative package suite, and uses a real Chromium browser
against the byte-identical source standalone HTML at both narrow/mobile and
desktop widths. It requires **46 checks in each**, including WebCrypto,
private local recovery and zero network requests, before uploading the
ZIP. These are desktop Chromium emulated layouts, **not Android hardware**
acceptance. The generated ZIP is accessible via the run's GitHub artifact
for seven days; it does not update the live Render site.

## Launch boundary

This is a no-cost, **human-testable prototype**. It is not the complete
authenticated NEXUS Rust service, not the Stage D Railway volume, not
a production restore witness, and not a Seal. The outstanding Render
auto-deploy and GitHub branch protection controls (#154, #168) remain
blocking for mainline production promotion. Do not merge this PR into
`main` just to create the artifact; PR CI produces the kit independently.

`A_out <= A_in`; evidence is not authorization.
