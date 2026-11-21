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
