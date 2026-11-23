# NEXUS Studio — local claim-review foundation (23 November 2026)

## Purpose
AI answers can contain plausible but unsupported factual claims. This module prepares an **unverified reading checklist** for the human reviewer. It does not make judgments, score truth, call a model, search the web, or assign authority. It follows the NEXUS separation between machine assistance and human judgment.

## Implementation

`web/studio-claim-review.js` exposes `globalThis.NexusClaimReview.review(text)` and `checklist(text, language)`. Both run locally with no network, storage, model, or dependency. The input limit is 24,000 UTF-16 code units. The module considers at most the first 12 distinct prose candidates (numbers/dates, causal/associational language, comparisons, or general declarative statements). It excludes Markdown fenced code, simple headings, table rows, questions, and certain instructions. Every returned candidate is **not-checked**, and the report explicitly sets `verified:false`. The checklist supports English (`en`) and Persian (`fa`), and is plain Markdown that the operator can inspect before manually saving or sharing.

A small pattern-based credential preflight stops extraction and Markdown checklist export when recognizable GitHub, API, AWS, Bearer or private-key shapes appear. Only fixed category names are returned on block. This detector is **not comprehensive DLP**, so it can miss personal data, unknown or encoded secrets, and may flag harmless test strings.

## Verification

```bash
node --check web/studio-claim-review.js
node scripts/test-studio-claim-review.mjs
python3 scripts/test-studio-claim-review-browser.py
```

Synthetic tests cover English and Persian, duplicate text, exclusion of code/questions, upper bounds and non-echoing credential blocks. They do **not** establish truth detection, source retrieval, model quality, browser integration or production deployment.

## Release boundary / next increment

This is a **source-only developer preview**. Open `web/studio-claim-review-demo.html` alongside its two local JS files to try the opt-in input and inert claim cards. It is **not yet in the NEXUS Studio chat controls or compiled static public bundle**. The isolated DOM acceptance runs with injected, unchanged source scripts in real Chromium but does not inspect deployed CSP/network behavior. A future reviewed increment can add an opt-in `Review claims` action on a selected answer, render text strictly as inert content, allow a human to add verified sources manually, and add real-browser acceptance. No automatic export or submission should occur. Do not advertise the feature as live until that UI, offline/static packaging and independent acceptance all pass.
