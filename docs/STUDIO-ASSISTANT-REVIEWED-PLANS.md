# NEXUS Assistant — reviewed workflow preview (API candidate)

This change adds an operator-authenticated, consent-gated preview endpoint:
POST /studio-api/assistant/plan-preview. It maps a short human-authored English
or Persian sequence into a structured, review-only checklist of existing Studio
tool destinations. It does not make NEXUS an autonomous agent.

## Request contract

Use the independently configured NEXUS_STUDIO_TOKEN (not a provider API key).
Send one application/json content-type, exact Boolean consent: true, and a goal
of at most 1,800 characters. The transport body limit is 8 KiB.

Example:

    {"consent":true,"goal":"Research ethical AI then analyze CSV data then draft a report"}

Or:

    برنامه:
    ۱. پژوهش درباره یک موضوع
    ۲. تحلیل داده‌های CSV
    ۳. بنویس گزارش

The response contains 2–6 ordered items with a canonical, existing tool name
(/research, /data, /write, etc.), the original instruction and a not_started
status. Every item requires independent human review.

Only explicit steps are accepted. Generic single-goal instructions cannot be
converted into credible action plans by this bounded offline classifier.
English 'then' and Persian 'سپس' are recognized separators. Unqualified
'and'/'و' are never silently promoted to new actions.

## Authority, security, privacy

- No model call, connected-account action, shell command, outbound request,
  archive read, repository modification, publication or execution takes place.
- The preview is NOT an approval token. The user must operate and approve each
  separate tool using its existing permission gates. A checklist is not proof
  that any step succeeded.
- Existing Studio destinations are allowlisted: research, data, writing, code,
  music, reminders, reviewed GitHub PR listing and Render deployment status.
  No arbitrary URLs, payments, email sends, destructive commands or GitHub
  writes are planned.
- Operator authentication is required even without a model provider.
  Malformed, oversized, unsupported, ambiguous, or compound steps fail closed.
- Responses carry Cache-Control: no-store. Sending the goal to this endpoint
  sends it to the NEXUS Studio gateway, not to an AI provider. This route does
  not implement storage or training. Gateway operators remain responsible for
  their own hosting/logging practices.
- Future UI clients must render untrusted instruction fields with textContent,
  preserve draft/conversation scoping, and retain explicit human approvals.

## Verification and delivery

Cloud regression tests cover authentication, consent, bounds, English/Persian
routing, ambiguity and no-provider-contact. Run the exact PR-head cloud
contract workflow before merge.

Not included: AI-generated planning, autonomous execution, tool chaining,
workflow persistence, new chat UI controls, a deployed service or proven
integration to an external provider. This is a backend API source candidate
for subsequent reviewed UI integration.

## Chat interface integration (stacked UI candidate)

The focused Studio chat adds an explicit **Plan steps** button. With a nonempty
human-authored 8–1,800-character draft, the user can preview the **exact**
text in a temporary panel. Clicking **Approve gateway-only preview** sends
that text to the configured NEXUS Studio gateway with the existing Studio access
token. There is **no** automatic request from typing, opening the plan panel,
changing tabs, or merely choosing a model mode. No provider model is called.

The browser strictly validates the returned schema and only permits the eight
reviewed tool routes. Every step must be an unmodified substring of the user's
draft and is displayed using textContent. An invalid, oversized, or failed
response becomes a visible error and never a runnable step. Editing the draft,
changing the conversation or clearing the private session revokes the preview;
in-flight responses are aborted or discarded. Every step must still be opened
and manually marked complete with the existing review-only workflow surface.

The original local **/plan** command remains available without any gateway
connection, account or external request. This new preview button requires a
configured gateway and operator-issued Studio token; the optional public
static website does **not** provide a gateway credential by default. It does
not turn NEXUS into a fully autonomous assistant. A staged UI result is not
an execution receipt, and no changes are made to the Rust constitutional
execution boundary.

Bundled Studio pages and the integrity-pinned static PWA worker must be rebuilt
from the exact source before release. CI and real-browser tests for the PR head
must pass; no live publication is asserted.

## Scoped, read-only execution receipts (stacked candidate)

An assistant plan can now distinguish three outcomes:
- **Gateway read returned (source content untrusted):** an explicitly approved
  GitHub open-PR or Render deployment-status read returned through the existing
  Studio connector, passed the connector's response validation and matched the
  exact current workflow step. The user then separately confirms the step.
- **Confirmed by user:** the user opens another tool and manually reports
  completion; NEXUS has no independent tool result for that step.
- **Skipped by user:** the step was bypassed and must never count as done.

The read receipt is held only in the current browser tab's checklist. It is
not saved to a chat, memory, archive, API, telemetry or external account. It
does not carry provider payloads or secrets and is NOT cryptographic
attestation of factual accuracy, timing, completeness or provider identity.

A connector opens with a one-shot, scoped callback only for the reviewed
read-only operations `github.pulls` and `render.deploys`. The callback
fires only after the separate human-approved read has received a validated
connector response; opening a dialog, loading an account catalog, changing
an operation or receiving an error is NOT sufficient. A callback cannot
authorize a second read or perform a write.

Editing the exact draft, switching project/conversation, clearing the
private session or reopening the workflow invalidates the old checklist.
Late callbacks cannot advance newer steps. The existing connector also
discards stale results on navigation, changed token or closed dialog.
Read-operation mismatch and explicit operator selection changes revoke the
pending receipt listener.

This is an incremental **human-in-the-loop workflow progress engine**, not
autonomous tool chaining, scheduled execution or durable execution evidence.
Read-only connector data is still untrusted, and all access permissions remain
on the gateway/connector. External tool success cannot establish a human
judgment under the NEXUS constitutional core.

The browser regression verifies that dialog opening and catalog browsing
are not receipts, an approved provider read enables an exact-matching step,
the user must confirm that step, and skipping/cancellation are reported
honestly. Review the exact PR head's CI before merging or publishing.

## Browser-observed local research and code completion (stacked candidate)

Two additional *real* tool-result paths now participate in the reviewed workflow
checklist, for both the local `/plan` command and the optional gateway plan:

- **Research:** the user must open the Research tool, approve the query in its
  own consent control, and obtain at least one source lead from a completed
  provider request. The result is explicitly **untrusted source material**, not
  proof that the claims in it are accurate.
- **Code:** the user must open the local JavaScript sandbox, separately approve
  the exact code and input, and receive a nonempty result from a completed
  isolated worker run. This is a browser-observed execution, not an independent
  security attestation. The worker has a runtime limit but no hard memory cap.

Opening a panel, using an old result, entering a failed query, stopping a run,
or merely checking consent does not unlock workflow completion. Each success
notifies a **single, ephemeral, kind-matched callback** armed when the exact
reviewed step opens. The callback is consumed on success and carries only
the type and, for research, exact approved query; it does not copy code,
answers, research data or credentials to a persistent store. A new workflow,
skip, draft edit, changed chat or private clear invalidates the callback and
pending receipt. **User confirmation is still a separate click** after the
tool completes, and skipped/self-reported/observed steps are separately
counted.

The operation-mapping rule also narrows GitHub read receipts: only a request
that would actually open the `github.pulls` review action can earn an
approved read receipt. Merely mentioning GitHub in a gateway plan cannot turn
branch/file/write instructions into successful read receipts.

The browser regression now tests an invalid research run, a successful
consented new research run, a fresh local code run, rejection of old code
output as a new receipt, and explicit skip/revocation behavior.

This does **not** add automatic web searches, remote code execution, provider
account mutation, recurring jobs, memory creation, or autonomous model calls.
Research and code still use their existing separate human-approval interfaces,
and all tool outputs remain untrusted until reviewed.

## Source-hashed, locally observed data-analysis steps (stacked candidate)

The `/data` step now uses the same **separate result confirmation** as
consented research and local JavaScript execution. Opening the analysis panel,
having a report left over from a previous run, or selecting a file never
unlocks completion.

- The user chooses a local CSV/TSV/JSON file or an applied project source,
  then explicitly clicks the existing **Analyze selected data** button.
- The data tool runs in the browser under its existing 1 MiB, 5,000-row and
  40-column capacity bounds. It rejects duplicate JSON keys, unsupported
  structures, invalid UTF-8 and oversized inputs under its existing rules.
- Only after table parsing, numerical analysis and SHA-256 hashing have
  succeeded does the tool emit a **single-use, temporary callback**. The
  callback carries the result kind, row and column counts, and the 64-digit
  source-content SHA-256. It contains **no raw file bytes, filenames, table
  rows, rendered summaries, model prompts or provider credentials**.
- The chat validates the receipt kind, provenance, hash shape and numeric
  bounds. It then enables a **separate confirmation** click. The hash
  identifies input bytes; it does not certify the source or the conclusions.
- Starting another analysis supersedes an earlier in-flight operation. File
  replacement, cancellation, project navigation and private clear prevent
  stale completions from rewriting a newer analysis. A skipped or discarded
  step cannot reuse a prior receipt. The original local analyzer does not
  transmit the file to a provider.

Browser regression covers an intentionally malformed duplicate-key JSON file,
a subsequent successful CSV analysis, and confirmation remaining disabled
until the fresh result actually arrives. This is an observed local computation,
**not autonomous model analysis, a verified scientific conclusion, or a
durable audit record**.

The new quality UI dependency is explicitly declared in Studio's deterministic
module graph. The packaged standalone and installable public shells have
their SHA-256 digest, length and service-worker cache identity re-pinned.
The HTML remains under the reviewed 630,000-byte public asset ceiling.

## Observed document version application and safe manual retry (stacked candidate)

A reviewed `/write` step is no longer equivalent to opening the writing
canvas or checking a box. The user must explicitly create/select a document,
edit text, and click **Save new version** in Studio's existing versioned
writing canvas. The app's ordinary `mutate` call must validate and apply
the new document version before the assistant receives a one-time completion
notification. An empty document, unchanged text, canceled or failed state
validation, or simply creating a document **does not** count as success.

The receipt contains only: operation kind `write`, an opaque new version
identifier, text length, and `persistence: session_only`. It carries no
document content, title, file, attachment, or model prompt. A receipt only
unlocks a separate confirmation for the currently active exact workflow
draft and conversation. A new workflow, explicit skip, private clear or
discard invalidates earlier receipts. The assistant counts an applied
document version separately from gateway reads, local computation and
self-reported outcomes.

**Important:** an *applied* document version exists in the currently
unlocked or temporary project/session. It is NOT guaranteed to survive tab
close. The user must explicitly save the encrypted browser archive or
export the document, and keep backups separately. The assistant does
not silently persist, export, upload or publish anything.

A reviewed step's **Review or retry tool** control only re-opens its tool
and revokes any earlier step receipt. It never automatically repeats a
network request, code execution, document save or external account write.
After an invalid or duplicate save, the user can correct the editor text
and manually click Save new version again.

Browser regression exercises no implicit document creation, no premature
completion on opening the canvas, no success from empty/identical saves,
successful new changed-version application, safe explicit retry with proof
revocation, and non-replay of an earlier session's writing receipt. All
UI and PWA shells are rebuilt with deterministic module order and re-pinned
hashes; the hard public size cap remains enabled at 635,000 bytes.

## Reviewed document exports: Markdown, DOCX and Print/Save as PDF (stacked candidate)

The temporary chat-first workflow now includes explicit `/export` as a local
review action. It opens the existing writing canvas without exporting anything.
A separate action on that canvas is required:

- **Markdown:** the user explicitly approves plain-text output and clicks
  **Export Markdown**. The browser is given a Blob URL and an explicit
  `download` click. The output can come from an unsaved editor draft or a
  saved version; the UI records which one was requested.
- **Word:** the user explicitly approves unencrypted output and clicks
  **Download Word**. A valid, nonempty document is serialized through the
  existing local DOCX generator before its Blob URL is clicked. Rejection,
  invalid content or generation failure cannot create a completion receipt.
- **PDF:** the user clicks **Print / Save as PDF**, reviews the plain-text-only
  document print surface and uses their browser's print dialog to choose
  **Save as PDF**. NEXUS does not itself create, download, or certify a PDF.
  Print CSS hides all other Studio body children; the ephemeral print surface
  contains only the document title and text using `textContent`. It is
  removed on `afterprint`, error, private clear or a bounded fallback.

Only the **browser request** is observed. A receipt contains a typed
`download_requested` (Markdown/DOCX) or `print_requested` (browser print)
status, the output type, a bounded size for generated downloads (0 for print),
and whether the editor content matched its latest saved version. It carries
**no document text, filenames, access tokens, content excerpts or source
data**. The user must independently check that the file was saved, opens,
and faithfully represents the intended document. Neither a download click
nor a print dialog proves delivery to disk.

A new workflow, opening the review tool again, explicit skip, goal edit,
project/thread change or private clear invalidates the previous one-shot
receipt. Other downloads (language packs, chat responses, backups) do not
count toward a document export step. No tool runs automatically, no model
or external provider receives the document, and the workflow does not
silently save to the encrypted archive.

Real browser regression checks rejected plaintext export, empty Word output,
unrelated downloads, Markdown and DOCX request receipts, explicit retry and
non-replay, a failed browser print, an isolated document-only print sheet,
print cleanup, no unauthorized provider calls and separate counts for
download versus print requests.

The reviewed source and standalone/PWA shells remain within a strict
645,000-byte HTML limit, with SHA-256 and service-worker cache re-pinning.
This is a **draft development candidate**, not a live production release.

## Export workflow preview parity (stacked API candidate)

The authenticated `plan-preview` endpoint now recognizes the existing Studio
`/export` destination in short explicit English and Persian instructions,
such as `Draft a report then export document as DOCX` or
`بنویس گزارش سپس خروجی سند به PDF`. This fixes a mismatch with the
chat-first review UI's already-supported document-export workflow.

The response is **only a plan preview**: each export step starts at
`not_started`, opens the existing writing canvas only after separate human
review, and neither generates a file nor establishes that a download reached a
device. Markdown/DOCX require a further user-approved browser download request.
PDF still uses a user-initiated browser print dialog and unverified Save as PDF.
No server-side export endpoint, provider call or automatic document transmission
is added. Because the local Code Lab only runs reviewed JavaScript, natural
language requests to *run Python* are now rejected instead of being mislabeled
as a runnable JavaScript step. English/Persian compound export instructions
without an explicit ordered separator are rejected.

Tests cover the route shape, bilingual inputs, rejected compound instructions,
Python mismatch, consented gateway response and zero tool/model execution.
This remains an unmerged candidate until branch-specific CI and browser
acceptance pass; it is not a published service.
