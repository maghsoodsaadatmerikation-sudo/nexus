# Studio local correction experience import

Development candidate, not a deployed feature. Open Project assistant & memory in an unlocked archive with a regular selected conversation. Expand **Import a reviewed correction report**, choose a local UTF-8 JSON file (1–65,536 bytes), and review the operation. Approval changes the local session only. Use **Save session** separately to persist the encrypted archive.

## Report contract

- Top-level fields: `schema` = `nexus.experience-review.v1`, `workflow_id`, `operation`, `criteria`, `attempts`. No other top-level fields.
- Operation: `kind` (`accept` or `refresh`), `criterion_id`, `correction_code`.
- Criteria: 1–30 records containing `id`, `required`, `evidence_kind` (human_review, automated_check, or independent_witness). At least one required criterion.
- Attempts: 2–12 records containing `correction_code`, `before`, and `after`. Each before/after run has a `scope` and `observations`. All runs must identify the selected project and report workflow. Scope fields: `project_id`, `workflow_id`, `run_id`, `plan_sha256`. An observation repeats these scope fields and supplies `criterion_id`, `evidence_id`, `kind`, and `result` (pass, fail or inconclusive). Use distinct actual run and evidence identifiers; do not fabricate reports or reuse receipts.
- The existing engine requires at least two reported failure-to-pass associations for a candidate with no reported regression or unsupported attempt for that correction.
- Accept adds an entry; refresh re-evaluates an existing entry. A separate management panel allows revocation and deletion.

## Limits

The import does not verify signatures, causal effectiveness, chronology, or whether a supplied report omits failed attempts. It cannot grant permission, apply a correction, or train a model. Only approved summary metadata is added to session state; the raw report is not saved or injected into model context. File selection remains local. Project/workflow labels are consistency checks, not evidence authentication. Prior backups and source files are not erased when a stored entry is removed.

The importer accepts structured reports; the integrated chat candidate can also generate a report and explicitly retain its reviewed metadata. Saving the encrypted session remains a separate step.

## Read-only recall adapter (development source only)

`web/studio-experience-archive-recall.mjs` bridges the validated archive and existing review engine. It requires an explicit recall opt-in, a live unlocked regular thread, matching project/workflow/thread and session/snapshot revisions, a present reported failure, and freshly supplied historical evidence pairs. It suppresses recall when required evidence is contradictory, rejects reuse of current run or evidence IDs, and excludes revoked or changed-support entries. Missing historical reports produce no recommendation. Counts are associations, not causality or authenticated evidence. The adapter does not save, modify, apply or inject any correction into model context. Its 35 synthetic regression checks are in `scripts/test-studio-experience-archive-recall.mjs` and wired into Studio CI.

The adapter is deliberately not bundled or wired to the chat UI yet; the host must separately gather consent, bind live session state, review any resupplied report and discard results when scope changes. No public deployment or feature acceptance is claimed.
