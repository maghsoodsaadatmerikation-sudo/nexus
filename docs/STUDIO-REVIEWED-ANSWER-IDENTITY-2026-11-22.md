# NEXUS Studio — verified model-route replies (22 November 2026)

## Problem

A gateway may expose multiple independently reviewed model routes. A model's
public display name is not a unique route identity. Previously Studio checked
the reply's public model name but could not reject an answer from the wrong
slot or a stale configuration. It also did not retain model-route attribution
alongside the encrypted conversation.

## Reviewed reply contract

New gateways advertise `reply_receipt_version: 1` on the existing, public,
read-only `GET /studio-api/status` when configured. Every **successfully
completed** reply from this gateway must contain the exact server-owned
`model_slot` and `configuration_id` bound to the reviewed request.
Streaming replies include both fields only in their final `done` frame.

Studio compares the reply to the exact context the user approved:

- `model_slot` must match the selected route (`primary` by default).
- `configuration_id` must match the reviewed fingerprint.
- The existing model-name, origin and non-authoritative checks still apply.

If the gateway advertised v1, a missing, partial, or mismatched receipt is
rejected before a message enters the chat tree. For older gateways that do
not advertise v1, replies without receipts retain a legacy, unattributed
fallback; however **any explicit receipt** must still match, even on a
legacy gateway. Users should upgrade their private gateway to enable strict
verification. A legacy result is not represented as a verified route.

## Session and history

For a matched receipt, Studio stores an optional, bounded
`model_receipt` object with that response's `model_slot`, `model`, and
`configuration_id`. The state validator permits this object only on
model-origin assistant nodes and rejects malformed slots, hashes, empty
identities, or additional fields. Older archives and local guide messages
remain compatible and unchanged.

The conversation shows the reviewed gateway model name and slot next to
that response. Transcript exports include the same label. The raw answer
body stays unmodified so copied text and editable documents remain useful.
The identifier belongs to the encrypted archive when the user explicitly
saves it. Imported archive contents are still user-supplied data, not an
independently signed attestation.

**Scope:** This checks which gateway route NEXUS accepted, not that an
upstream provider is independently authenticated, that its answer is correct,
or that any payment/provider access is available. Nothing can execute tools
from a model reply. Human consent and decisions remain mandatory.

## Regression evidence

Run these offline, deterministic checks in the checked-out repository:

```sh
cd nexus-cloud
uv sync --frozen
uv run --frozen pytest -q tests/test_studio_model.py tests/test_studio_multi_model.py
cd ..
node scripts/test-studio-core.mjs
python3 scripts/build-studio.py --check
python3 scripts/build-studio-static.py --check
python3 scripts/test-studio-browser.py
python3 scripts/test-studio-model-receipt-browser.py
```

A separate real-browser witness covers the receipt scenarios on fresh
narrow and wide Studio sessions so its acceptance checks remain inside the
strict 60-second per-browser deadline. The general Studio witness remains
bounded and independently runs its existing broader workflow.

Tests cover a matching model response, wrong slot, wrong configuration,
missing or partial v1 receipts, streamed wrong-slot completion, validated
archive round-trips, and inert, readable provenance labels.

No live model calls, provider credentials, public deployment, billing
changes or user archive migrations are performed by this change.
