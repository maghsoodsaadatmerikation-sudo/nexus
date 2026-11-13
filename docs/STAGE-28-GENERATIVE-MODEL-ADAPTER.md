# Stage 28 — actual opt-in generative model adapter (not a provisioned model)

NEXUS was previously **extractive** and had no general text-inference backend.
This stage implements the authenticated HTTP path and a client for a real
OpenAI-compatible text model *when* an authorized operator provides credentials.
It does not create model weights, a no-cost provider account, a user identity,
model training, web search, autonomous tool use or a live hosted deployment.

## Enabling (only by the authorized owner/operator, on a trusted private gateway)

Defaults OFF. No model call is attempted when unconfigured. For a compatible
provider, the operator chooses exactly one:
- NEXUS_MODEL_PROVIDER=openai (pinned POST to
  https://api.openai.com/v1/chat/completions);
- NEXUS_MODEL_PROVIDER=groq (pinned POST to
  https://api.groq.com/openai/v1/chat/completions).

Set NEXUS_MODEL_ID to the actual provider-supported model ID and
NEXUS_MODEL_API_KEY as a *server-side* environment secret, not a repo file,
browser-visible value, PR body, issue, screenshot or plaintext export.
Provider accounts, plan limits, quotas, charges, terms and data retention are
operator-dependent. For a truly zero-budget operator, leave the feature off
until a suitable permitted, provisioned free/local provider exists. No hidden
fallback, fake completion, automatic switch or unaudited endpoint is allowed.

The owner must accept all costs before enabling. This stage sends no funds,
creates no paid service or registers any provider account. It does not
auto-launch from the user phone or edit Railway configuration.

## Human/client flow

Open /model-chat on a trusted authenticated NEXUS gateway.
Enter NEXUS's private gateway token, type a message and separately consent to
(1) this EXACT conversation and (2) provider processing/potential costs.
Approval is per request, consumed before sending, and reset on edits.
NEXUS forwards only the alternating submitted messages plus the static
non-authoritative system constraint; there are no project files, memory,
workspace, history store, tokens or plugin results implicitly attached.
A new server request always needs fresh confirmation.

The server returns schema nexus.model-chat.v1, exact configured provider/model,
mode generative_unverified_machine_draft, authority=none,
judgment_changed=false, verified_facts=false, citations=[], actual_cost_known=false
and automatic_actions=false. Model answers are unverified drafts and are never
human judgment, policy, execution authorization or factual citation.
No tool capabilities or remote function execution are offered to providers.
Model answers are not persisted by this endpoint.

Requests are limited to 1–12 alternating human/assistant messages, max
1500 Unicode characters/message, max 24000 UTF-8 bytes total, ending in a
human message. Model output max 6000 Unicode characters. Upstream budget:
512 output tokens (provider may count reasoning tokens), 2 concurrent model
calls, 5-second connect timeout, 25-second total call timeout, 27-second
backend deadline, 40 KiB max upstream response, redirect disabled, proxy
disabled, TLS to two exact public destinations and provider credentials
server-side only.

Authentication, recovery quarantine, HTTP body size, rate limits, private
no-store response headers and request capacity controls are inherited from
NEXUS's core gateway. Calls never occur automatically and cannot set task
status, approve/execute actions, write workspaces or mutate policies. Provider
errors are intentionally generic; no provider error body or token is surfaced.

## Verification

- Rust tests exercise disabled state, consent/ack requirements, accepted
  model-draft schema, exact alternating-message boundaries, malicious
  credential strings, unconfigured providers, invalid content and zero
  authority.
- Browser tests mock only the server transport to verify user-consent
  gating, no auto-network, unknown-model errors, cancellation, inert text
  rendering and no session/localStorage or account token export.
- CI compiles the full Rust gateway and existing code, ensures default
  unconfigured state makes no external network requests, and keeps the Stage27
  Android preview offline/no INTERNET permission unchanged.
- **Not** a paid/free live provider integration proof. A separate
  owner-approved real-provider witness with quota and privacy controls is
  needed before a production feature-release claim.

## Next independent capabilities

User requested all other ChatGPT-style features; see issue #142.
Next independently testable steps: multimodal image parsing/generation,
Deep Research over reviewed sources, bounded file transformations, Android
real storage-recovery/backup and durable opt-in scheduled tasks. All require
their own browser/mobile acceptance and must preserve A_out <= A_in.
