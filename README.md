# NEXUS

**Constitutional infrastructure for human judgment.**

NEXUS is a Rust-based constitutional core, epistemic workspace, authenticated HTTP gateway, browser client, and verification pipeline designed to help humans examine questions, evidence, alternatives, uncertainty, and consequences without transferring meaning, identity, or final decision authority to a machine.

## Core principle

> **NEXUS may assist judgment; NEXUS must not own judgment.**

The system separates human authority, evidence, machine analysis, execution authority, and auditability. The constitutional invariant remains:

```text
A_out <= A_in
```

## Try NEXUS on the web (static, no account)

The English-first multilingual mobile pilot is hosted at
**https://nexus-offline-pilot.onrender.com/**. Render reported LIVE for
manual deployment `dep-dbqt14ff3r2c73drgirg` of Pilot 18
source commit `ffa41c01a9f0311e7005db7abaef56585591645b`.
The independent static HTTPS identity workflow pins the actually deployed
source; provider status alone is not byte-level proof. The app does not
connect to the Rust gateway, send workspace content to Render, or issue
machine decisions. Export a separate password-protected file to preserve
work beyond one browser.
See [Pilot 02 hosting and independent HTTPS evidence](docs/STATIC-PILOT-HOST.md)
for what has and has not been verified. The full authenticated online pilot
remains a separate open milestone.

## Installable offline on Android and supported browsers (Pilot 12 candidate)

Pilot 12 now adds **آماده‌سازی حالت آفلاین** and
**افزودن به صفحهٔ اصلی**. The user can explicitly cache an integrity-pinned
app shell and reopen it after network loss; the app shell never caches
workspace JSON, password or personal information. Saving work still
requires the separate encrypted local checkpoint or owner-held file.
The standalone HTML continues to work when opened from a downloaded file.

Render reported LIVE for static deployment `dep-dbqt14ff3r2c73drgirg`
from exact source `ffa41c01a9f0311e7005db7abaef56585591645b`.
Independent public asset-byte checks and live-origin real Chromium offline
acceptance must PASS separately; provider LIVE alone does not prove them.
[Installation and security contract](docs/PILOT-12-INSTALLABLE-OFFLINE.md).

## Readable local decision report (Pilot 13)

The public static app adds a Persian read-only report of recorded questions,
evidence, alternatives and human judgment, with explicit plaintext text-download
and print/PDF actions. Unsubmitted drafts and passwords are excluded; committed
changes invalidate an older preview. No option ranking, remote transmission or
new storage. [Report behavior and verification](docs/PILOT-13-READABLE-DECISION-REPORT.md).
Published on the existing static site; independent public browser acceptance
checks both the workshop and report. Real Android print/PDF behavior still
depends on the browser and device.

## Uncommitted text protection (Pilot 14)

A visible indicator distinguishes unregistered form text from committed work.
New, Demo, import and encrypted local restore require confirmation before
replacing drafts. Changes during local decryption abort replacement. Export
warnings explain that drafts are excluded; no draft storage or automatic
human judgment is introduced. [Behavior and browser limits](docs/PILOT-14-DRAFT-PROTECTION.md).
Published to the existing static site. Independent public Chromium acceptance
checks draft protection, the report, the workshop and actual offline navigation.
Browser exit prompts remain conditional; mobile OS termination is not guarded.

## English-first interface and local translation packs (Pilot 15)

English is the default. Complete English and Persian interfaces can be switched
without changing workspace contents. A full local language pack can add any
BCP 47 language with LTR/RTL direction. The downloadable English template
contains only interface text. There is no automatic network translation and
no claim that every language has a bundled reviewed translation.
[Language support and pack format](docs/PILOT-15-ENGLISH-FIRST-LANGUAGES.md).
Published on the existing static site. Independent public Chromium checks
English default, Persian switching, custom packs and unchanged private work.

## Microphone and read-aloud (Pilot 16)

An opt-in Voice panel reads a chosen field/report and turns speech into a
reviewable preview, then an unregistered draft. Passwords are excluded and
human judgment still requires explicit registration. Local processing is the
default; browser online speech needs a separate opt-in and per-action consent.
Support depends on installed device/browser speech capabilities.
[Voice behavior and verification limits](docs/PILOT-16-VOICE-INPUT-OUTPUT.md).
Published on the existing static site. Public adapter tests are separate
from physical device audio; supported voices/languages vary by device/browser.

## Local files and document generation (Pilot 17)

Add any file type to this open tab (10 MiB each, 20 MiB/20 files total), preview
text/source and bounded Office XML text, and explicitly copy an excerpt into
an unregistered evidence draft. Generate TXT, Markdown, CSV, HTML, genuine
DOCX/XLSX, XML or a ZIP containing the current originals; PDF uses browser print.
Files are not server uploads or part of the encrypted workspace checkpoint.
[File formats, preservation limits and independent validation](docs/PILOT-17-LOCAL-FILE-DESK.md).
The file desk was deployed and independently tested on public HTTPS in
Pilot 17; the Pilot 18 promotion retains the same protections.

## Local exploratory data analysis (Pilot 18)

The file tray now offers an explicit **Local data analysis** panel for
CSV, TSV, flat JSON object arrays and bounded XLSX sheets. It calculates
descriptive numeric statistics, missingness, categorical frequencies, group
comparisons and pairwise Pearson correlations in-browser, and offers simple
distribution bars and an explicitly confirmed aggregate JSON export.
A selected summary can become only an **unregistered machine-analysis draft**;
it never automatically establishes truth, a human judgment or an audit event.
No file or analysis is uploaded to the static Render server. Inputs are limited
to 1 MiB, 5,000 rows and 40 columns; XLSX formulas are rejected rather than
executed. Analysis exists in this tab only, and the summary JSON is unencrypted
and may include private category labels.

[Supported inputs, statistics, limits and acceptance](docs/PILOT-18-LOCAL-DATA-ANALYSIS.md).
Published by a manual deploy of the existing static site at the exact Pilot 18
source. Source reviews and standalone Chromium analytics tests passed before
merge; the separate public-acceptance workflow verifies the actual published
HTML, file analysis, language, voice adapters and offline reopening. These
synthetic tests do not prove real-human operation or physical device support.

## User-directed Internet research (Pilot 19 candidate)

NEXUS adds a **Web research** panel with 15 built-in public search destinations,
an optional custom HTTPS query-URL template and direct public HTTPS navigation.
Only a user-confirmed browser link opens an external provider in a separate
no-opener/no-referrer tab; the provider, not NEXUS, processes the search.
NEXUS does not scrape result pages, access third-party search APIs, automatically
verify results or independently support every engine on Earth. The static
application retains CSP `connect-src 'none'`, and manually typed queries
are never copied from workspaces, files or passwords. Users may paste a short
reviewed passage and public HTTPS source into an **unregistered evidence draft**;
human verification and registration remain necessary. Custom templates and
searches stay in the current page session.

[Security, available engines and limits](docs/PILOT-19-WEB-RESEARCH.md).
The candidate must pass real-browser verification, a separate manual deploy
to the existing static site and independent public acceptance before it is
represented as published.

## Recoverability check for private encrypted files (Pilot 11)

Pilot 11 adds **file-picker verification of an actual downloaded encrypted JSON file**, with the original passphrase, against the *committed* workspace. This does not replace the workspace, upload it or claim that the file is safe outside the device. The independent HTTPS observer checks the published source. [Pilot 11 details](docs/PILOT-11-VERIFIED-ENCRYPTED-EXPORT.md).

## Try NEXUS now — free offline decision pilot

The deployed Pilot 09 adds a one-click, visibly fictional first-run exercise
that creates evidence and alternatives but **no human decision**, and never
asks for personal information. This is strictly a browser-only demonstration.
See [Pilot 09 contract](docs/PILOT-09-GUIDED-FIRST-RUN.md).

A [standalone Persian mobile decision workshop](web/offline-pilot.html)
is available without a hosting account, device setup, API token or ongoing
service. **Download the HTML file and open the downloaded file in your browser**;
GitHub's source preview is not the running app. See the
[offline-use and privacy guide](docs/OFFLINE-PILOT.md).

This is a local, explicitly exported/imported demo whose **core editing makes no application network requests**. Optional browser speech services may use provider networks only after explicit choice and confirmation.
The current source adds **optional, explicit-consent encrypted browser-local
checkpoints**, off by default; they are not remote backups or proof of original
Railway data recoverability. This is not the sealed Rust gateway,
a live production instance or an attested audit. The optional Pilot 06 plaintext Rust v1 export reconstructs an explicitly unattested event stream for a separate authenticated import; it never connects to the server. See [bridge contract](docs/PILOT-06-OFFLINE-RUST-BRIDGE.md).
A real authenticated online user pilot is tracked separately in [Issue #70](
https://github.com/maghsoodsaadatmerikation-sudo/nexus/issues/70).
The original Railway storage must not be modified before independently
verified recovery.

## Current sealed release — v2.5.0

`v2.5.0` is the current sealed **unified transport-authentication** boundary.

It preserves the earlier constitutional, runtime, capability-enforcement, revocation, and gateway authority-confusion boundaries while requiring configured bearer authentication before request parsing, constitutional delegation, or request-status lookup.

### v2.5 release boundary

- Exact release candidate: `200ff827efed0a165548e9dbc2b6801d23d6ddfb`
- Invariant: `A_out <= A_in`
- NEXUS v2.5 Unified Transport Authentication Verification run `36385219907`: SUCCESS
- Canonical NEXUS Verification run `36385219924`: SUCCESS
- Release Gate run `36385267448`: SUCCESS
- Exact-candidate evidence attestation: VERIFIED
- Missing and incorrect credentials: REJECTED FAIL-CLOSED
- Authenticated `POST /v1/requests`: asynchronous `202 Accepted`
- Authenticated `GET /v1/requests/{id}`: status/`404` semantics preserved
- Release evidence SHA-256: `c64546d8b96e99338ba9cc41a93e0f825b151e8627b436d321ade31b5a432c46`
- Production mutation: NONE
- Authority expansion: NONE

The v2.5 seal is a **transport-authentication boundary**. It does not claim credential rotation, external identity federation, rate limiting, distributed session state, durable persistence, consensus, universal security, or external-system linearizability. Authentication permits access to a transport boundary; it does not create constitutional authority.

Historical release tags remain immutable earlier boundaries. In particular, v2.0 remains an unsealed engineering milestone; later releases do not retroactively seal it.

## Architecture

```text
Human
  |
  v
Browser / Authenticated HTTP Product
  |
  v
Epistemic Workspace
  |-- Question / Goal
  |-- Claims + Provenance + Uncertainty
  |-- Alternatives + Consequences
  |-- Machine Analysis (non-authoritative)
  |-- Explicit Human Judgment
  |-- Append-only Audit History
  |
  v
Constitutional Core
  |-- Authority boundary
  |-- Policy decision
  |-- Authorized request
  |-- Executor
  |
  v
Verification / Evidence / Attestation
```

The gateway may parse, validate shape, create envelopes, delegate, and serialize responses. It does not independently authorize, deny, interpret evidence meaning, execute constitutional actions, or mutate policy.

## Current single-host pilot

Later engineering commits add durable request admission, full-data recovery,
write quarantine, liveness/readiness and bounded storage-failure defenses. They
require their own exact-commit verification; the historical v2.5.0 Seal does not
cover them. See [single-host completion and operator entrypoint](docs/SINGLE-HOST-COMPLETION.md).

## Run the gateway locally

```sh
export NEXUS_API_TOKEN='replace-with-a-long-random-secret'
export NEXUS_DATA_DIR='./nexus-data'
export NEXUS_BIND_ADDR='127.0.0.1:3000'

cargo run --manifest-path artifact-05/Cargo.toml --locked
```

## Verification

The verification workflow preserves the rule:

> **No real verification -> no claim of PASS -> no seal.**

Continuous verification runs on source changes and at 00:00, 08:00, and 16:00 UTC. Scheduled verification may observe, verify, attest, and report; it carries neither release authority nor production-promotion authority.

## Repository map

```text
src/                                      Constitutional core + epistemic engine + adapters
artifact-05/                              HTTP gateway and product contract tests
artifact-06/                              Synthetic Reality Lab contract and CT-001..020 map
artifact-07/                              Public-exposure safety controls and evidence contract
web/                                      Browser workspace client
docs/DEPLOYMENT.md                        Deployment contract
docs/RELEASE-v1.1.0.md                    Sealed durable-host release record
docs/RELEASE-v1.2.0.md                    Sealed operational-resilience record
docs/RELEASE-v1.3.0.md                    Sealed production-hardening record
docs/RELEASE-v1.4.0.md                    Sealed deployment-truth record
docs/RELEASE-v1.5.0.md                    Sealed promotion-safety record
docs/RELEASE-v1.6.0.md                    Sealed exact-promotion record
docs/V1.7-ROADMAP.md                      Runtime-provenance roadmap and completed gates
docs/RELEASE-v1.7.0.md                    v1.7 release record
docs/V2.2-REVOCATION-REPLAY.md             Revocation replay integrity contract
docs/RELEASE-v2.2.0.md                    v2.2 sealed release record
docs/V2.3-REVOCATION-FRESHNESS.md           Stale-authority defense contract
docs/RELEASE-v2.3.0.md                    v2.3 sealed release record
evidence/v1.7/production-runtime-evidence.json
                                           Production runtime-provenance evidence
.github/workflows/v1.7-runtime-identity.yml Independent runtime identity reconciliation
.github/workflows/v1.7-production-reconcile.yml
                                           Public production runtime reconciliation
.github/workflows/release-v1.7.yml          Fail-closed v1.7 release gate
.github/workflows/verify.yml                Verification, evidence, and attestation
```

## Releases

- NEXUS v2.5.0 — Unified Transport Authentication Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v2.5.0
- NEXUS v2.4.0 — Gateway Authority-Confusion Defense Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v2.4.0
- NEXUS v2.3.0 — Revocation Freshness / Stale-Authority Defense Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v2.3.0
- NEXUS v2.2.0 — Revocation Replay Integrity Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v2.2.0
- NEXUS v2.1.0 — Capability Enforcement Boundary Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v2.1.0
- NEXUS v1.7.0 — Runtime Provenance Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.7.0
- NEXUS v1.6.0 — Exact Promotion Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.6.0
- NEXUS v1.5.0 — Promotion Safety Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.5.0
- NEXUS v1.4.0 — Deployment Truth Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.4.0
- NEXUS v1.3.0 — Production Hardening Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.3.0
- NEXUS v1.2.0 — Operational Resilience Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.2.0
- NEXUS v1.1.0 — Durable Host Verification Sealed: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.1.0
- NEXUS v1.0.0 — Constitutional Infrastructure: https://github.com/maghsoodsaadatmerikation-sudo/nexus/releases/tag/v1.0.0
