# Pilot 06 — Offline mobile workshop → Rust core (explicit, unattested conversion)

## What changed

The one-file Persian mobile HTML gains **فایل انتقال به هستهٔ Rust (بدون رمز)**.
The button constructs a `schema_version: 1` Rust `WorkspaceSnapshot` locally,
using the complete currently visible `nexus.offline-pilot.v1` workspace.
Nothing is sent to Railway, Render APIs, an online account, or another user.
The converted JSON is **plaintext**, explicitly user-confirmed, and distinct
from the original protected `nexus.offline-pilot.encrypted.v1` vault.
Keep the original encrypted file as the only protected user-held backup.

The generated file can later be posted by a separate authenticated operator
to the Rust gateway's `POST /v1/workspaces/import` route on a **recovered,
approved host**. Pilot 06 does NOT post to any live host and is NOT a
production migration. Never upload actual private conversions to the public
repo, GitHub Actions, issue threads, or a shared cloud browser.

## Mapping details

- Preserve the **current** question and workspace ID, goal (empty becomes
  `null`), constraints and values verbatim; preserve ordered claim IDs,
  content, uncertainty and external source label verbatim.
- Human claim: `Human`; imported machine-origin claim: `MachineAnalysis`
  with **`ClaimAdded` only**, not `MachineAnalysisRecorded` because the
  offline tool has no verified machine-adapter invocation.
- External claim: `{"ExternalEvidence":{"source":"..."}}`; uncertainty
  becomes the Rust enum `Unknown/High/Medium/Low`.
- Preserve all option labels, IDs, consequences and their order. Do not
  auto-rank or infer the best one.
- Import a human judgment **only** if the offline record has an explicit
  judgment event and non-empty judgment. Legacy locally imported v1
  documents with an empty rationale may be converted without inventing one.
- Rebuild the Rust event stream from local **event types and order**, starting
  at `WorkspaceCreated` sequence 0. Skip repeated local question edits,
  since the Rust v1 schema has no event for them. Emit new `ClaimAdded`,
  `AlternativeAdded` and, only if present, `HumanJudgmentTransition`.
- Every reconstructed event uses the explicit source marker
  `offline-bridge:user-supplied-unattested` — the original offline
  timestamps, machine adapter identifiers, independent provenance, auth
  history and event signatures are **not transferred**. These are a newly
  reconstructed audit representation; they do not certify original history.

Conversion fails closed when the v1 in-memory state cannot pass the
existing offline format/history/ID validator. No destination overwrite is
attempted, even locally; the JSON download is a new file. The Rust backend
refuses duplicate workspace IDs with HTTP 409.

## Actual disposable Rust integration evidence

The `.github/workflows/offline-pilot.yml` run, on an exact proposed source
SHA, uses real Chromium in narrow and wide viewports, with a synthetic
question, claims (including a machine-origin claim), alternative and explicit
human judgment. It tests the bridge before and after judgment, checks source
mapping, reconstructed audit and user confirmation, and confirms zero network
attempts. Synthetic core output is written only into a private CI temp file,
excluded from the published browser witness.

The CI job then builds the actual Rust Docker gateway and creates an
ephemeral token and storage directory bound to loopback. It posts the
**Chromium-produced** JSON directly to the actual authenticated
`/v1/workspaces/import`, verifies denial of missing/wrong bearer, expects
HTTP 201 on first import and HTTP 409 on duplicate, exact JSON readback and
durability after a container restart; invalid audit content must be denied
with HTTP 422. Only the sanitized booleans and synthetic SHA-256 are uploaded.
No personally identifiable data, authentic production tokens, production
volumes or public Rust endpoints are involved.

## Self-critique and remaining barriers

1. **A Rust snapshot is not a full-volume backup.** Request ledgers,
   provider lifecycle, historical timestamps and original server state
   cannot be reconstructed from a browser file.
2. **Provenance is not attested.** Local event history can be edited by a
   person. Events are explicitly marked user-supplied and reconstructed;
   conversion does not make them authentic, and it must never silently
   promote machine analysis into a human decision.
3. **Plaintext exposure.** Server-compatible v1 snapshots are plaintext.
   If a human later imports the file, they must intentionally choose a
   trustworthy, authenticated, independently recoverable deployment.
4. **Duplicate workspace IDs and schema upgrades.** The gateway may reject
   an existing ID or future schemas. Pilot 06 targets **only** the current
   Rust v1 gateway and does not automatically migrate future schema changes.
5. **CI locality.** Real Chromium + real Rust HTTP is meaningful for schema
   compatibility, but not evidence of a human's private data on the original
   Railway host or independently recovered durable production storage.

The first real-host pilot in Issue #70 and the independent Railway `/data`
backup+restore gate remain open. No additional constitutional authority or
Seal is granted: `A_out <= A_in`.
