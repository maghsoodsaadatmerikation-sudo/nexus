# NEXUS Offline Pilot — a usable single-file mobile prototype

**Scope:** offline, one-person decision-structuring prototype; no Rust engine,
no public endpoint, no authorization, no automated machine decision, no
provider-backed persistence. This is not a production deployment or an
authenticated single-host NEXUS service.

## Use from an Android phone or desktop

The file is [web/offline-pilot.html](../web/offline-pilot.html). Download **the
HTML file itself** from the repository and open it in a browser capable of
running local HTML. A code preview is not the app; a rendered offline file is.
The repository's GitHub Pages setting was observed disabled on 2026-11-10,
so there is currently no verified public web-app URL. Do not claim otherwise.

1. Enter a question, a goal, constraints and values; press **ثبت مسئله**.
2. Record externally sourced claims with source identifiers and uncertainty,
   options with possible consequences, and review them independently.
3. Only your click on **ثبت تصمیم من** can create a human judgment.
4. Press **دریافت فایل JSON** after meaningful changes. Save that private file
   in storage you control. There is **no autosave** and all unsaved state is
   lost upon reload/close. Data is retained in memory while the page is open.
5. On later visits choose **بازکردن فایل قبلی**. Only this offline v1 format
   is accepted; malformed/corrupt history is refused without replacing the
   current workspace. The file should be treated as **sensitive plaintext**.

This offline JSON is not a Rust gateway-compatible
`nexus.data-snapshot.v1` or server `DecisionWorkspace` backup; do
not import it through the production workspace restore endpoint or represent it
as an independent Railway volume backup. It lacks the request ledger,
gateway authentication, cryptographic audit checks and provider continuity.

## What the file can and cannot do

The page is a dependency-free Persian RTL HTML document with a restrictive
Content Security Policy, no image or network requests, no browser storage, and
explicit export/import. It displays user-supplied strings as text rather than
injecting HTML, validates source requirements for external evidence, enforces
bounded form/input limits, and tracks a basic event history. The history is
**not cryptographically attested** and cannot be treated as independent
provenance, historical proof, an authorized request, or proof of recovery.

The core constitutional principle remains: evidence does not become authority,
machine notes do not become human judgment, and execution authorization is not
present in this demo (`A_out <= A_in`).

## Real-browser verification

`python3 scripts/test-offline-pilot-browser.py` opens the unmodified product
in real headless Chromium at a narrow and a wide viewport, in private temporary
profiles. It checks question/goal/constraints, missing-source rejection,
escaped evidence, non-authoritative machine analysis, options, explicit
judgment, JSON download structure, re-import, corruption rejection, and zero
network calls. The program exercises only synthetic user content; CI never
receives real personal data, operator tokens, or Railway resources.

The test report means **only a standalone file prototype was exercised**.
Actual Android hands-on usability, server data durability, public GitHub Pages,
a production-authenticated session, independently verifiable provider backups
and multiuser privacy are not proven.

## Next verified decision

The hosted product remains the actual NEXUS Rust/browser stack described in
[the first-user acceptance contract](PILOT-01-FIRST-USER.md). Offline use is an
interim, no-cost access path, **not** permission to restart/deploy the original
Railway service with an attached production volume. Use Issue #70 to track the
real-host pilot and restore/backup gaps. No paid services are required for the
offline HTML or its standard public-repository CI tests.
