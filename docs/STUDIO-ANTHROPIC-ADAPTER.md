# NEXUS Studio: native Anthropic Messages adapter

An **optional, text-only, non-authoritative** provider adapter for NEXUS
Studio. This is the Anthropic native Messages endpoint, not OpenAI-compatible
Chat Completions. NEXUS does **not** provision a model or key, perform live
provider testing, cover billing, or turn the model into an autonomous agent.

## Scope and safeguards

- The existing browser request preview and explicit user consent, separate
  operator authentication, 42-message limit, body/response byte bounds,
  provider attempt budget, concurrency and 45-second deadline still apply.
- NEXUS sends its server policy as the top-level Anthropic system prompt and
  the reviewed history as only user/assistant messages.
- Adapter anthropic requires the **exact** URL
  https://api.anthropic.com/v1/messages, an operator-selected model ID, a
  server-only provider key, and a Studio token of at least 32 characters.
- Requests include x-api-key and anthropic-version: 2026-10-21. The Studio
  operator bearer is not sent to the model provider. The API version is bound
  to the reviewed configuration fingerprint.
- Only buffered responses work. Native Anthropic SSE differs from the
  OpenAI-compatible streaming protocol; setting NEXUS_MODEL_STREAMING=1
  deliberately **disables** this provider configuration until corrected.
- The request does not grant tools, computer use, beta features, MCP servers,
  file or Internet access, or extended thinking features.
- NEXUS accepts only text blocks from a completed assistant message with a
  recognized end_turn or max_tokens stop reason. Tool use, thinking blocks,
  unknown/partial/refusal stop reasons and invalid Unicode fail closed. A
  max_tokens result is labelled truncated.
- There are no live paid requests, provider credentials, user prompts, files,
  or production deployment changes in this PR.

## Operator-only environment settings

Supply actual secrets only in private server configuration, never in source
control, screenshots, URLs, issue comments or chat:

~~~sh
NEXUS_MODEL_ADAPTER=anthropic
NEXUS_MODEL_URL=https://api.anthropic.com/v1/messages
NEXUS_MODEL_ID=OPERATOR_SELECTED_SUPPORTED_MODEL_ID
NEXUS_MODEL_API_KEY=SECRET_IN_PRIVATE_SERVER_ENVIRONMENT
NEXUS_MODEL_WORKSPACE_ID=OPTIONAL_WRKSPC_ID_FOR_UNSCOPED_KEY
NEXUS_STUDIO_TOKEN=RANDOM_PRIVATE_TOKEN_AT_LEAST_32_CHARACTERS
NEXUS_MODEL_STREAMING=0
NEXUS_MODEL_MAX_REQUESTS_PER_PROCESS=8
~~~

For keys that are not scoped to a workspace, Anthropic requires the
anthropic-workspace-id request header. NEXUS sends this only when the operator
sets NEXUS_MODEL_WORKSPACE_ID to a valid wrkspc_ identifier in the private
server environment. Invalid or misplaced workspace IDs disable the model
configuration before any outbound model request. Workspace ID is included in
the reviewed configuration fingerprint and never returned in public model
status or authenticated readiness responses. Keys created for one workspace
normally require no additional workspace selector. This is not a user-selectable
browser setting or an authorization bypass.

One provider adapter is active per server configuration. Reconfiguration of
provider identity, policy or API version changes the reviewed ID and requires
new user consent. The operator must separately confirm API model availability,
geographic eligibility, provider retention practices and spend/usage limits.
The optional one-host durable attempt counter cannot replace provider-side
spend caps and is not cross-host.

## Offline verification

From the nexus-cloud directory:

~~~sh
uv sync --frozen
uv run --frozen pytest tests/test_studio_anthropic.py tests/test_studio_model.py
~~~

The suite uses only HTTPX mock transport with synthetic data. No API keys,
paid provider calls, or public service verification are involved. A green
offline suite does not prove a live Claude model can be used.

## Official protocol references

- https://platform.claude.com/docs/en/api/messages/create
- https://platform.claude.com/docs/en/api/versioning
