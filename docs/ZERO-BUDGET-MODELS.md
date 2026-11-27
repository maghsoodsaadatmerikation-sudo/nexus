# NEXUS without a paid model subscription

## Device-first entry

The static Studio package now lists **On-device AI** in its tool browser,
chat tool directory and suggestion chips. `/device` and `/local-ai` offer the
same reviewed handoff. Opening the card preserves the message draft, starts no
download or model request, and creates no conversation. The card is placed in
the visible workspace rather than left inside collapsed model settings.

Check device readiness, review the roughly 167 MB download, and explicitly
allow loading. Then choose **On-device small model** in model settings and
prepare and approve the exact request. The existing SmolLM2-135M route supports
short English drafts: 768 input tokens, 64 output tokens. It is not a verified
Persian assistant or a replacement for a large model. Device/browser support,
storage, download access, battery use and physical Android speed still matter.
No account or provider API key is needed for this local route. See
[device model limits and verification](DEVICE-MODEL.md).

## Optional online route with free-only restrictions

Configure the existing gateway through private server settings:

| Setting | Value |
| --- | --- |
| `NEXUS_MODEL_ADAPTER` | `openrouter-free` |
| `NEXUS_MODEL_URL` | `https://openrouter.ai/api/v1/chat/completions` |
| `NEXUS_MODEL_ID` | An available, explicit `owner/model:free` identifier |
| `NEXUS_MODEL_API_KEY` | Operator's OpenRouter key, stored only on the server |
| `NEXUS_STUDIO_TOKEN` | Separate private gateway credential, at least 32 characters |

The adapter rejects missing keys, other endpoints, paid identifiers, model
suffix modifiers, and dynamic `openrouter/auto` or `openrouter/free` selection.
An explicit model is required so quality evaluation has a stable selected model
identity. Availability can still change upstream.

Each buffered, streamed and quality-evaluation request sends a zero maximum
prompt, completion and per-request price, disables provider fallbacks, and sends
one selected model without a fallback list. Standard execution mode only is
supported. The existing consent, configuration fingerprint, request capacity,
attempt budget, bounded responses and no-automatic-retry rules remain in force.
Rejections and exhausted free quota never initiate paid or local fallback.
An operator can still configure other adapters separately; this is a restriction
of the `openrouter-free` route, not an account-wide billing control.

An account and key are still required. This patch supplies neither, does not
purchase credits, and does not enable a live public provider. As checked on
27 November 2026, OpenRouter documents 50 daily and 20 per-minute requests for
free variants without a credit purchase; failed attempts count. Upstream limits,
model availability, regional eligibility and data policies must be checked for
the actual account. The gateway's local allowance is a separate attempt guard,
not a measurement of remaining OpenRouter quota or independent billing proof.

Use this route for an initial pilot. Local calculations, file tools and charts
can avoid model calls; using them does not create stronger language reasoning.
The shared free allowance cannot support unlimited global traffic. No quality
claim for Persian or other tasks is made before a live evaluation.

Primary references:

- https://openrouter.ai/collections/free-models/
- https://openrouter.ai/docs/guides/routing/provider-selection
- https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct

## Validation

```sh
uv run --frozen --project nexus-cloud pytest -q nexus-cloud/tests
python3 scripts/build-studio.py --check
python3 scripts/build-studio-static.py --check
node scripts/test-device-model-readiness.mjs
```

Synthetic tests cover rejected paid/ambiguous configuration, zero-price buffered
and streamed payloads, evaluator parity, and no extra provider attempt on
payment, quota or availability rejection. Static browser acceptance includes a
visible no-key tool handoff with preserved draft, no download, and no new chat.
The local Chromium binary is unavailable in the current development workspace;
the new browser assertion requires CI before claiming a passed browser result.
