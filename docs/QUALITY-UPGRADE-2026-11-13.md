# Integrated quality upgrade — 13 November 2026

Baseline: `35be3d4b0da0d0f21e04a4a8a61f45e316a0058e`.
This release improves existing workflows and shares their implementation. It is
not a claim that all possible improvements are complete or that NEXUS has a
frontier generative model.

| Area | Concrete change |
| --- | --- |
| Data analysis | Studio can analyze bounded local CSV/TSV/flat JSON and applied project sources, show grouped statistics, copy a draft summary to writing, export JSON and send validated groups to the chart tool |
| Shared implementation | The existing offline data desk and Studio use `web/table-core.js` for parsing, normalization, descriptive statistics, grouping and correlation; their numerical rules no longer drift independently |
| Numerical reliability | Scale-aware mean/variance and Pearson arithmetic reduce overflow; convex-interpolation quantiles avoid subtractive overflow; nonrepresentable results are null; local Persian/Arabic digits are accepted; ambiguous separators and unsafe plain integer strings are not guessed |
| Missing categories | A genuinely empty group and the literal label `(missing)` are counted separately, with an explicit missing flag |
| Source retrieval | Whole Unicode tokens, deterministic case/Arabic–Persian normalization, CJK character/bigram features and length-normalized term-frequency/rarity ranking replace raw substring counts |
| Provenance and bounds | Source passages retain source ID/name, line, UTF-16 character offset, matched terms and score. Search caps at 12,000 passages; truncation is shown in source results and the reviewed model context |
| Public research | Wikipedia generator results respect provider search rank instead of numeric object-key order; source text remains inert and unverified |
| Charts | A one-point line chart now has a visible data marker; analysis-generated charts use the existing validator and PNG export path |
| Recovery | One explicit Undo restores the most recent applied project/chat/document/source/astrology removal, including graph/version data. Any later data mutation invalidates it; a structural comparison rejects stale restoration |
| Privacy | Undo is bounded, volatile tab memory and is cleared on lock, archive replacement/unlock and erase. Local data jobs/results clear on project change/lock; late completions cannot repopulate the cleared session |
| Interface | Tool navigation, visible keyboard focus, bilingual capability status and keyboard shortcuts improve access without bypassing exact-send review |

## Scope and limits

- A local dataset is bounded to 1 MiB, 5,000 rows, 40 columns and scalar cells.
  Legacy XLSX admission/ZIP/formula controls remain in the existing file desk;
  the new Studio dataset input accepts CSV/TSV/JSON only. Studio project source
  imports retain their existing smaller limits.
- JSON numbers and descriptive calculations use approximate binary64 arithmetic.
  This is not an exact financial calculation engine, causal analysis, statistical
  significance test, clinical appraisal or proof that source values are correct.
  Unsafe plain integer strings are kept categorical; they must not be silently
  treated as exact numerical identifiers. Extreme/unrepresentable results are
  null rather than serialized as a claimed finite value.
- Top value/group labels and chart labels may be shortened. Group lists retain
  the existing 12-group preview limit; full source rows are not exported in the
  report. Correlations use pairwise-complete numeric cases. Report exports can
  still reveal sensitive category labels and require the normal plaintext-export
  confirmation. Files/results are never added to model context automatically.
- The summary copied to a selected document is a draft until a version is saved.
  The original document version is preserved. Raw temporary datasets and reports
  are not automatically archived; explicitly import a source or save a summary.
- Retrieval is bounded lexical ranking, not semantic embeddings or universal
  linguistic segmentation. CJK features are characters/bigrams, not a claim of
  perfect word boundaries. No source statement becomes a verified fact merely
  because it ranks highly. Source removal clears stale source-search displays.
- Undo restores applied state only, not unsaved form text, erased archives,
  external actions or another browser tab. It stores one bounded before/after
  pair in tab memory, and never overwrites a different intervening data state.
  Recovered applied data still need explicit encrypted session save.
- Ctrl/Cmd+Enter in the message box prepares a configured model request, or runs
  the local guide. Ctrl/Cmd+Shift+S saves an already unlocked archive. Escape
  cancels waiting work. A shortcut never grants model/network consent.

## Existing capabilities preserved

Immutable conversation branches and document versions, optional project memory,
explicit public retrieval, encrypted archives/CAS, reviewed model transport,
opaque-origin code isolation, local sky computation and separate optional natal
personalization remain covered by the required existing tests. General sky tone
still affects presentation only, with its existing visible off switch. It does
not change data/statistical rules or create a new decision authority.

The production model variable names were inspected without reading or printing
secrets. No `NEXUS_MODEL_URL`, `NEXUS_MODEL_ID`, `NEXUS_MODEL_API_KEY` or
`NEXUS_STUDIO_TOKEN` is configured there. This work does not manufacture a model
credential or disguise the local guide as generative AI. The capability display
separates local tools, internet-dependent research and configured model access;
image generation, real-time voice, unattended jobs and authenticated app actions
are still not supplied by these integrations.

## Verification design

- 47 new contract checks exercise reference means/median/SD/Pearson/group counts,
  quoting/newlines, malformed/bounded tables, local digits, unsafe integer
  strings, overflow-scale values, distinct missing labels, whole-word and
  multilingual retrieval, search truncation, guarded Undo and Wikipedia rank.
- A new real Chromium witness exercises actual source/data files, numerical
  output, summary-to-version flow, analysis-to-chart JSON, a real one-point
  Canvas pixel, project/chat/document/source recovery, keyboard behavior,
  export provenance and lock/late-result isolation with website networking off.
- Existing real offline data-desk acceptance is required against the same shared
  module, including its XLSX path. Existing Studio, astrology, sky and code-lab
  tests are required before merge. Browser model responses in existing fixtures
  are transport tests, not evaluations of a real model's output quality.
- Deterministic builders update both the standalone Studio bundle and the legacy
  offline app/service-worker content hash. Snapshot schemas, native APK files
  and production user records are not migrated or rewritten by this release.
