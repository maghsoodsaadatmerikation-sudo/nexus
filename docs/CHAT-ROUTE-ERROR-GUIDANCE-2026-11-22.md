# Model route mismatch: actionable chat feedback

A strict NEXUS Studio gateway advertises `reply_receipt_version: 1`.
When a completed buffered or streaming answer has a missing, partial or
mismatched `model_slot` or `configuration_id`, the browser rejects it
**before** updating conversation state. The user's unsent draft is preserved.

Previously, these errors appeared as a general `Operation failed` or
streaming failure, making the next step unclear.

The chat now explains, in English or Persian, that the reply did not match
the model or configuration the user explicitly approved, that no answer was
added, and that the user should check the gateway and review a new request.

This does not attempt an automatic retry: upstream traffic may already have
been billed, and another request requires fresh exact-context review and
explicit consent. In particular, the text must not assert that the upstream
provider is independently verified.

The label is optional for installed third-party locale packs: older packs
remain valid and fall back to the built-in English explanation where needed.

## Synthetic offline regression

```sh
python3 scripts/build-studio.py --check
python3 scripts/build-studio-static.py --check
python3 scripts/test-studio-model-receipt-browser.py
```

The real Chromium scenario checks that the invalid reply is rejected without
committing or deleting the unsent draft; both English and Persian recovery
messages appear. No live provider calls, credentials or public deployment
are involved.
