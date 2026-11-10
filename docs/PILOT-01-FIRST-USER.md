# NEXUS Pilot 01 — first usable judgment workflow

**Status: gated; no live human production pilot completed.** This document
separates four distinct facts: checked-in product functionality, synthetic
real-browser/real-gateway use, public read-only host observation, and a real
human's authenticated workspace on durable externally recoverable storage.

## Intended actual first-user journey

An operator on a mobile browser, without a local Rust/Docker install, should
be able to:

1. Visit the existing HTTPS origin and check service readiness.
2. Enter an operator-provided private bearer credential *in the runtime token
   field*, never in a URL, issue, git commit, public artifact or chat message.
3. Ask one real question and create a Decision Workspace.
4. Add evidence with an identifiable source and explicit uncertainty.
5. Add alternatives with their consequences; verify machine observations
   have not silently populated the human judgment.
6. Explicitly record *their own* judgment and rationale.
7. Download the authenticated workspace JSON, store it somewhere private and
   independently accessible, close/reopen the browser, reload the workspace
   and confirm the audit history and human decision remain intact.

The JSON workspace export is **not** a complete operational backup: it does
not include the durable request ledger, recovery quarantine state, credentials,
provider snapshots, or every possible file from `/data`.

## What is already implemented

- `web/index.html` provides creation, evidence/provenance, alternatives,
  explicit human judgment, audit history and verified JSON export/import.
- `artifact-05` provides the authenticated gateway with durable workspace
  state and a separate request ledger.
- `scripts/verify-single-host.py` has already tested real HTTP workspace
  mutation, request retention and container replacement on disposable CI
  volumes. Browser DOM witnesses elsewhere used synthetic transport.
- `scripts/pilot-01-real-browser.mjs` bridges that test gap. A real
  Chrome instance loads the original gateway-served application and clicks
  through creation, evidence, alternatives, human judgment and JSON download.
  It then restarts its uniquely named **throwaway CI container**, opens a
  fresh browser, first checks unauthenticated loading is refused, and then
  confirms the persisted JSON digest, visible history and explicit decision.
  Both 390px and 1280px viewport classes are exercised. Test transport is
  genuine loopback HTTP; data and credentials are synthetic and temporary.
- `.github/workflows/pilot-01.yml` runs only standard GitHub-hosted
  CI jobs. It creates a newly named disposable volume in an isolated runner,
  removes it afterward, and uploads **only sanitized test results**.
  No operator deployment, secret or real user workspace is touched.
- `scripts/observe-pilot-01-public-ui.py` compares the actual public
  HTML response with the UI in the source **pinned by Railway**. It performs
  a single public GET, never a POST, and never supplies credentials. Its
  results are non-authoritative observations, not proof of data durability.

## Current public-host constraint (observed 2026-11-10)

Railway service `nexus-stage-d`, project `NEXUS Stage D`, still points
to deployed code `3c0977f4c7fc9fb5e9a78bdb1eeb581cb3cb4959`.
The checked-in main branch is already at later code. The deployed
`web/index.html` differs from current main: at this baseline it lacks the
new readiness observation and retained request-status UI. GitHub merge or
a passing synthetic browser test does not promote this newer UI to Railway.

The production volume `cc47a350-6c7e-4487-89d9-c4b390f94884` remains
mounted at `/data`; attached does not mean recoverable. Current independent
backup/export freshness, content, and actual restore have not been proven.
The connected Railway integration does not expose volume file download or
private production credentials. No redeploy/rollback/restart of the original
volume is authorized merely to run Pilot 01. Existing [Issue #66](
https://github.com/maghsoodsaadatmerikation-sudo/nexus/issues/66) continues
to track that gate.

## Promotion / real-user acceptance gates

- **Synthetic product flow**: complete browser+gateway round trip on a
  disposable, isolated CI volume, including export and process restart.
- **Current public frontend**: a read-only external HTTPS witness of
  page content and version, with no credential and no mutations.
- **Real authenticated session**: one operator-held credential must work
  against the actual exact deployed runtime. An automated CI credential
  from a throwaway container does not establish this.
- **Independent recoverability**: current exact production volume export,
  point-in-time consistency, checksum, isolated restoration and rollback
  anchor must be established before any production promotion.
- **Operator acceptance**: a human deliberately enters a genuine
  non-sensitive pilot question, evaluates claims, records their own
  judgment and independently checks the private export after reload.
- **Multiuser**: out of scope until authentication/isolation model is
  expanded beyond the current shared bearer-token model.

Any failed or missing gate is **OPEN / NOT PROVEN**; never report a real
production pilot, public launch, successful disaster recovery, new Seal, or
provider promotion from these tests. A_out <= A_in and evidence != authority.

## No-cost / no-device boundary

This project can prepare, verify and audit CI using GitHub-hosted standard
runners without a user's physical computer. Actual authenticated use still
requires a legitimate private credential from the hosting account, and
durable online use requires independently recoverable storage. Do not
solve that limitation by exposing tokens in GitHub Actions logs or publishing
a populated database through Pages or a public artifact. No payment or
provider change was made by this pilot implementation.
