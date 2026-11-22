# Studio chat: model readiness near the composer — 22 November 2026

## User-visible behavior

The **Check gateway settings** button in NEXUS's chat interface already
discovers configured model names from the public, read-only status endpoint.
If the user has supplied a Studio operator credential (at least 32 characters),
the same explicit click now also makes one authenticated read-only request for
the **currently selected** `model_slot`.

The chat model strip can then distinguish:

- `READY_TO_TEST`: local configuration and local budget permit a reviewed
  test. Shows the count of locally remaining attempts, not a model quality
  score or verified provider access.
- `LOCAL_BUDGET_EXHAUSTED`: the local attempt budget denies further calls.
- `LOCAL_BUDGET_UNAVAILABLE`: the local private budget storage is unavailable
  and provider calls fail closed.
- No trustworthy diagnostics (older gateway, invalid token, malformed
  response, network failure): fall back to **configured only** without
  alleging a successful live provider connection.

Switching model slots, changing the gateway address or rotating its token
invalidates the displayed readiness. The browser rejects diagnostics whose
slot, model, provider host, or no-provider-contact markers disagree with the
public catalog. No credential or budget is persisted in the chat archive.

## Security and operational boundaries

- Requires an intentional **Check gateway settings** click; no automatic
  provider call, no background polling, no billing.
- The operator token goes only to the user-configured, validated gateway
  origin. CORS remains subject to gateway policy; no cookies or redirects.
- Model generation still requires exact-context review and a separate
  consent approval for each message.
- Local budget may change after a check; the gateway remains the authority
  on whether a subsequent call is allowed.
- Browser reports do **not** establish upstream provider health, model
  accuracy, global billing quotas, or readiness for public release.
- This UI depends on the server-side per-slot diagnostic contract in PR #431.

## Verification

Run the deterministic bundle contract and real browser acceptance:

```sh
python scripts/build-studio.py --check
python scripts/test-studio-browser.py
```

The expanded Chromium scenario covers an explicitly authenticated readiness
lookup, per-slot budget rendering, zero provider calls, credential redaction,
slot-change invalidation and token-rotation invalidation. These are synthetic
offline checks; they are not evidence of a real funded provider connection.
