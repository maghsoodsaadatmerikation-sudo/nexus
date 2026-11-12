# Pilot 18 — Local data analysis, not automated judgment

Pilot 18 extends the English-first/Persian no-cost offline NEXUS workshop. A user
first adds an original file to the existing in-tab Files tray, chooses that file
under **Local data analysis**, and explicitly clicks **Analyze locally**. The app
does **not** send the file, analysis or workspace to any server or create a
question, claim, answer, audit event or human judgment automatically.

## Supported and bounded inputs

- CSV (comma delimiter and escaped quoted fields), TSV (tabs and quoted fields)
- JSON: one array of flat objects with scalar/null values, not arbitrary nested JSON
- XLSX: first numbered worksheet only; inline/shared strings and literal numeric
  cells, using the existing ZIP and XML guards. Formula cells, XML entities/DTDs,
  corrupt archives and unsafe paths are rejected, not executed.
- File size at most **1 MiB**; at most **5,000 rows and 40 columns** in the
  analytical table. Existing browser file-tray constraints also apply.
- No PDF OCR, image recognition, audio transcription, arbitrary source-code
  execution, SQL connections, spreadsheets with live formulas, statistical ML,
  automated causal inference or individual recommendations.
- Empty values are counted as missing. Numeric parsing is strict decimal-point
  notation with optional exponent. Mixed columns are described as categorical
  when fewer than 80% of nonmissing values parse as finite numbers.
- A row containing too many columns, a malformed quoted CSV, a non-scalar
  JSON property or an unsafe XLSX aborts the analysis. Unknown cells are never
  interpreted as scripts; all labels, categories and text appear as textContent.

## Analysis and interpretation

The report includes row/column counts, missing and distinct counts,
categorical frequencies, numeric count/min/max/mean/median/quartiles/sample
standard deviation, pairwise-complete Pearson correlation and selected
group-by count/numeric mean. Small bar histograms and groups are on-device DOM
renderings, not remotely fetched images. No hypothesis testing, p-values,
statistical significance, clinical conclusion or causal inference is claimed.
Columns with numeric-looking IDs can be misidentified; human review is required.

The full table remains in memory, *not* in the NEXUS workspace JSON,
encrypted local checkpoint, decision reports or external API. The explicit
**Download analysis** action creates an unencrypted JSON summary containing
the source filename and SHA-256, aggregate values and the top five distinct
category labels per column. These categories may themselves be identifying;
the download requires confirmation. It does **not** dump full raw rows.
The source SHA-256 verifies byte identity only, not truth or authorship.

The separate **Copy summary as unregistered claim draft** action uses origin
`machine_analysis`, uncertainty `unknown` and the local file hash as source.
The user must explicitly register any question and claim. No human judgment
is created or replaced. Replacing the workspace, changing/removing/adding
files or an in-flight file-read race invalidates the previous analytical view.
Changing language relabels the interface without altering private data.
Closing the page loses in-memory analytical tables and unarchived originals.

## Verification and deployment

- `scripts/build-ui-languages.py --check`: complete matching English/Persian
  application catalogs, identical standalone inlined analysis script, exact
  service-worker SHA-256.
- `node --check web/data-analysis-core.js`: strict syntax verification.
- `scripts/test-local-data-analysis-browser.py`: synthetic real Chromium on
  mobile-sized and desktop-sized viewports. It checks known numeric answers,
  correlation and group sample sizes, chart rendering, JSON output consent,
  no workspace mutation, bilingual interface, real generated XLSX re-import,
  rejected malformed/nested/over-limit inputs, late-result cancellation and
  zero application network/plaintext localStorage writes.
- Existing file, voice, language, report, offline-network and Rust bridge
  checks remain independent.

**Deployment gate:** review ALL checks on one exact PR head before merge.
Do not claim public Pilot 18 until the *existing* free static Render site is
manually deployed to the merged source and an independent public HTTPS
exact-byte/browser/offline witness passes. The historical Pilot 17 deployment
is the previous rollback/pinned public baseline. Keep Render autoDeploy off,
and do not change the original Railway volume or claim a new release seal.

Invariant: `A_out <= A_in` — data analysis is descriptive assistance,
not transfer of epistemic or decision authority.
