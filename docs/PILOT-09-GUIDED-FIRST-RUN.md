# Pilot 09 — a one-click synthetic, consent-safe first-run

## Objective

Give mobile users an immediately usable NEXUS experience **without entering personal content**. Render reported LIVE for the existing static site's manual deployment
`dep-dbqo0pei0phs73d8rrb0` of Pilot 09 source commit
`8e3fd8789d82db4559a9cb77cd2f82578271df4b` on 2026-11-12.
An independent pinned public-HTTPS source-byte check is a separate gate;
the provider's LIVE status alone is not independent proof.

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

The source was merged through PR #101 after six exact-head checks succeeded.
The Render static pilot had autoDeploy disabled; we explicitly triggered a
manual deployment of the existing Static Site only. The follow-up
`.github/workflows/static-pilot-https.yml` baseline pins the actual
Render-deployed commit. [Issue #100](https://github.com/maghsoodsaadatmerikation-sudo/nexus/issues/100)
tracks provider receipt, independent exact-byte public identity and
remaining honest production/nonclaims.

Do not spend money, modify Railway's original `/data` volume, claim an authenticated human pilot, Seal, Release, or expand authority. `A_out <= A_in`.
