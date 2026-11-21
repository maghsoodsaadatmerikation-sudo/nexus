# Studio chat model choice: truthful configuration at a glance

NEXUS Studio's focused chat composer now shows **what is actually configured**, rather than advertising models that a user cannot access.

## User interaction

- The response selector keeps its safe default: **Local reflection guide**. This is deterministic, not a generative language model, and sends no prompt to a model provider.
- Selecting **Connected AI model (requires approval)** reveals a compact model-status row.
- **Check gateway settings** explicitly checks the existing public `GET /studio-api/status` endpoint. This is **configuration-only** and does not make a model inference call, guarantee provider access, or establish answer quality.
- If the gateway has not been checked, the composer says so. When it has been checked, it shows the actual configured model ID and provider hostname as inert text. It does **not** show provider credentials, API keys, workspace identifiers or project data.
- Up to **three** models can now be **explicitly** configured by the operator on one gateway: the legacy primary model plus optional secondary and tertiary routes. The selector lists only routes that pass local configuration validation; it is not an online model marketplace.
- Switching the selected model updates the request review to include the **exact selected slot, model ID and configuration fingerprint**, and immediately revokes any previous consent. Selecting does not trigger a model request.
- Sending a real prompt still requires the existing exact-context preview and a separate explicit consent action. Provider-side charges and data policies may apply; a ChatGPT subscription is not an API key.
- Switching response mode cancels any pending model request review and unchecks approval. No provider request is issued by merely selecting a mode or inspecting status.
- Changing the configured gateway origin invalidates the old model status display without a network call; the user must explicitly check the new gateway.
- The existing advanced settings remain available. Temporary sessions, saved encrypted archives, files, memory and voice are not transmitted by the chooser itself.

## Verification

The existing disposable Chromium witness now tests:

1. The local guide is the initial default and the new model row is hidden.
2. A checked synthetic gateway reports only its actual configured model and explicitly warns real access is unverified.
3. Mode changes cause **zero** additional provider calls.
4. Changing the response mode revokes a previously prepared request review and consent without changing conversation drafts.
5. A two-route synthetic gateway is inspected from the chat, models can be switched without a provider call, and a separately approved request binds to the exact selected route.
6. Switching away from a reviewed provider keeps the user's draft but revokes the old approval.

The deterministic `scripts/build-studio.py --check` contract requires the standalone `web/studio.html` bundle to embed the exact modified source modules and stylesheet.

This is a UX and consent-boundary improvement, not a live model activation, production release or performance claim.