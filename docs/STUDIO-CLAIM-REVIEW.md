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
python3 scripts/test-studio-claim-review-chat-browser.py
```

Synthetic tests cover English and Persian, duplicate text, exclusion of code/questions, upper bounds and non-echoing credential blocks. They do **not** establish truth detection, source retrieval, model quality, browser integration or production deployment.

## Release boundary / next increment

The feature is now **integrated in the source Studio chat**: after an actual model response, select **Review claims / بررسی ادعاها**. A temporary panel below that exact reply displays up to 12 **not-checked** candidates. Close the panel, change conversation or language, or lock the workspace to discard the panel; it is not stored in the encrypted conversation archive. Synthetic provider browser acceptance checks this integrated workflow at narrow and wide widths. The separate source-only developer preview `web/studio-claim-review-demo.html` is retained for isolated testing.

The deterministic standalone and static Studio files are rebuilt with this code. Their service-worker SHA-256 digest and package ID are recalculated from the exact updated public HTML. **Deployment is not implied.** No real provider-backed claim verification, public-host witness or physical-device acceptance has occurred. A future independently reviewed increment may add explicit, opt-in source retrieval and verified source-provenance receipts. That is not provided by the current implementation. No automatic export or submission should occur. Do not advertise the feature as live until that UI, offline/static packaging and independent acceptance all pass.

## Increment: transient human evidence notebook (23 November 2026)

Each extracted model-answer claim has an expandable **Add human source note** editor. A user may enter one HTTPS source address (maximum 1,000 characters), an exact ISO publication date, a short manual note (maximum 500 characters), and their own assessment: *not assessed*, *appears to support*, *appears to contradict*, or *inconclusive*. A support/contradiction assessment is rejected unless an HTTPS URL **and** syntactically valid publication date are entered. Only user-entered inputs are recorded; NEXUS never opens the URL, reads the article, checks author/date accuracy, scores confidence, or decides truth.

The engine re-derives the exact claim from the original model answer and rejects unknown IDs, forged fields, malformed dates/URLs, overlong text, known credential patterns, or a review blocked for credentials. Its receipt has fixed \`verification=not-independently-verified\`, \`source_retrieved=false\`, and \`authority=none\`. The report generator revalidates the annotations, refuses duplicates, and never invents a source. A human may explicitly copy a plain-text Markdown review report after a separate unencrypted clipboard confirmation.

All notes are held **only in memory inside the open per-answer panel**. Closing the panel, re-rendering, switching chats/language, or locking discards them; they are not added to encrypted project archives and are never sent to providers. No automatic saving, exporting, analytics telemetry, or background source lookup occurs. The clipboard becomes an external plaintext copy only after affirmative consent; the user must separately manage that copy. URL validation and pattern scanning do not imply comprehensive privacy protection or source trustworthiness. UI uses inert DOM text, not HTML for statements or notes.

Synthetic Node tests and actual Chromium narrow/wide acceptance cover invalid source schemes, wrong dates, forbidden assumptions, confirmation/clipboard boundaries, isolation from chat archives, and zero additional network calls. Generated HTML and static offline cache digests must be checked at the exact PR head before merge. The feature is **not deployed** merely because the source and built files exist.

## Increment: source text / quotation presence check (23 November 2026)

The user may manually paste an excerpt of the independently obtained source (30–12,000 UTF-16 units) and an exact 30–400-character quotation, in addition to the source HTTPS URL and publication date. NEXUS runs a deterministic, local, case-sensitive string-presence test after NFKC and whitespace normalization. Results are only **present-in-user-paste** or **not-found-in-user-paste**, and disclose the matching count (capped at 99). The user may paste a forged document or excerpt; this feature does **not** authenticate it, validate the web page, assess the quote's relevance, resolve contradiction, or determine truth.

Source text and quotations are pattern-scanned for recognizable credentials (a limited heuristic) and never sent to a model, external website, or search endpoint. They stay in the open panel as unsaved transient state. The explicitly copied report may include the selected quotation and string-presence result, **but not the pasted source document**. The report generator re-runs the same check on its transient inputs and refuses unknown fields or fabricated "verified" flags. Closing the panel or changing the conversation/language clears these inputs.

The isolated Chromium test now exercises present/missing quotations, secret-shaped inputs, no network, explicit clipboard confirmation, omitted document text and ephemeral state; the Node test verifies malformed provenance, length limits, local matching, missing quotes and misleading claim-verification flags.

A regression in the prior plain-Markdown escaping helper was also corrected. The helper now escapes each character via a callback, so punctuation cannot accidentally interpolate an unrelated program source fragment into copied review notes.

These are checks of **user-pasted text**, not real web evidence. Future opt-in source retrieval would need a separate, security-reviewed proxy and clear user consent, SSRF/redirect controls, domain trust policy, caching/privacy review and real-source attribution. It is not part of this draft.
