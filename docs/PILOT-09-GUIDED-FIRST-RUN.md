# Pilot 09 — a one-click synthetic, consent-safe first-run

## Objective

Give mobile users an immediately usable NEXUS experience **without entering personal content**. The current hosted public Render version may still be the older Pilot 06 source; this code candidate is **not live on Render** until separately deployed and independently verified under Issue #100.

The demo is a single optional button above the existing workspace. It fills a visibly marked, fictional study-planning question, goal, constraints, values, exactly two sample claims and two sample alternatives. One claim's purported source is named `demo:synthetic-unverified-not-a-real-source`, never an actual provenance assertion.

## Constitutional safety

- Sample content is fully hard-coded and fictional; no new network calls, account, hidden AI analysis, external claims or third-party data.
- `authority:'none'`, `storage:'memory_only'`, `judgment:null`; **no** `judgment` audit event. This is not an actual human decision. The app does not rank options or decide for the person.
- Local event history is only a five-row illustrative sequence with correct schema; it is never an independently attested audit.
- If a prior question or unsent draft exists, opening the demo requires user confirmation and explicitly warns about data replacement. Declining preserves current work.
- The existing Pilot 08 encrypted checkpoint is **paused, not erased or overwritten** before opening the synthetic sample. The demo will not silently start encrypted autosave, which remains opt-in.
- Starting a new workspace discards synthetic data and restores the empty, human-controlled form.

## Verification

`scripts/test-offline-pilot-browser.py` now includes 40 assertions in each of mobile and desktop Chromium. It checks one-click synthetic population, exactly two claims/two alternatives, five audit events and no human decision, no browser checkpoint on a fresh profile, source labelled demo-only, exported schema and no authority, refusal to overwrite on denied confirmation, and new-workspace isolation. Existing encrypted export/recovery, real page reload, optional Vault protections, and Rust bridge checks continue unchanged.

No backend, provider or Railway action is needed. The GitHub CI success proves only **synthetic browser usability** and data/authority guard behavior; it does not establish real end-user acceptance, server durability or production recoverability.

## Promotion

After exact PR checks PASS, merge with expected SHA and verify main. The Render static pilot has autoDeploy disabled, so source merge does not make the new feature live. [Issue #100](https://github.com/maghsoodsaadatmerikation-sudo/nexus/issues/100) remains the tracked explicit selection, deployment and independent public-byte verification gate.

Do not spend money, modify Railway's original `/data` volume, claim an authenticated human pilot, Seal, Release, or expand authority. `A_out <= A_in`.
