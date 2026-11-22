# NEXUS AI reply identity receipts — 22 November 2026

## Purpose

When one Studio gateway exposes multiple separately configured models, the
client must be able to distinguish the **reviewed route** that generated an
answer from the model-generated words in the answer. Two routes may legitimately
use the same public model name, while using different operator credentials or
workspaces.

## Exact behavior

For successful **buffered** and completed **streamed** gateway replies, the
server now emits two additional metadata fields:

- `model_slot`: the server-selected `primary`, `secondary` or `tertiary`.
- `configuration_id`: the public fingerprint of the selected, reviewed
  server configuration at the instant the request is accepted.

The values come from the **frozen server-side `ModelSettings`**, after the
incoming request's `configuration_id` has passed review and before the
provider is contacted. They are never taken from the model's output, arbitrary
provider response metadata, or an unreviewed browser assertion.

The existing answer `text`, `model`, `truncated`, `origin`, and
`authority` fields remain unchanged. For streams, metadata appears only on
the final `done` frame, never on text deltas. Incomplete streams have no
successful receipt. The direct offline `response_frames` API remains
backward-compatible when no receipt argument is supplied.

This change does **not** prove the upstream provider's identity, quality,
liveness, trustworthiness, billing cost or factual correctness; it establishes
the **gateway routing selection** only. It grants no additional user or machine
authority and does not permit tool execution.

## Verification

```sh
cd nexus-cloud
uv sync --frozen
uv run --frozen pytest -q tests/test_studio_model.py tests/test_studio_multi_model.py tests/test_studio_anthropic.py
```

The existing real synthetic test fixtures validate that the completion identity
matches the reviewed route for each configured slot, including the legacy
primary wire contract and streamed completion.

No paid-provider calls, credential changes or deployments are made by this
change. A future UI update can use this metadata to reject mismatched responses
and show origin information for individual saved messages.
