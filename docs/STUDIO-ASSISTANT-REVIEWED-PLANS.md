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
