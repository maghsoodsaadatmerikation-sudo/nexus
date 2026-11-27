# Global Beta integration: provider launch and operational recovery

## Changes

The supervised local Studio launcher previously forwarded only four primary
provider settings. Streaming, Anthropic workspace routing and the secondary and
tertiary model slots were silently dropped. The launcher now shares the model
gateway's exact field allowlist and validates a private configuration snapshot
without temporarily modifying process credentials. An explicitly configured
but invalid slot blocks startup before private state is created.

Durable-budget diagnostics now recommend reviewing the persistent attempt limit
and provider quota when exhausted. Restarting the gateway is no longer suggested
as a remedy for a host-persistent counter. Process-only diagnostics retain their
existing behavior.

## Verification and limits

Real subprocess and loopback HTTP tests cover a streamed primary, independently
keyed secondary, configured Anthropic workspace, no startup model requests,
secret exclusion from status, and a two-attempt allowance surviving a restart.
The Anthropic workspace is checked without sending an external provider request.

Overlapping ASGI requests verify four active provider calls, refusal of extra
buffered and streaming requests before charging an attempt, responsive liveness,
and recovery after both completion and cancellation. Cancelled upstream attempts
are not refunded or replayed. This is bounded local concurrency verification,
not a global capacity benchmark.

```sh
uv run --frozen --project nexus-cloud pytest -q nexus-cloud/tests
uv run --frozen --project nexus-cloud python scripts/test-launcher-shutdown.py
```

The existing narrow/wide browser acceptance runner was attempted in this
workspace but could not start: `/usr/bin/chromium` points to a missing browser
binary. A separate disposable browser-runtime installation was attempted, but
the download endpoints rejected access. No UI acceptance or physical Android
result is claimed for this change.

## Remaining external release dependencies

| Blocker | Evidence still needed |
| --- | --- |
| Real model quality | Authorized provider/compute and live synthetic quality evaluation on the selected configuration |
| Deployed integration | Exact deployed commit, provider configuration, same-origin chat/tool/browser verification |
| Global operations | Hosting capacity, target-load results, provider quotas, recovery and rollback verification |
| Mobile experience | Working browser test runtime and physical Android acceptance |
| Independent validation | Security review and user trials on the release candidate |

No hosted model, budget purchase, deployment, security attestation or global
readiness percentage is created by this patch. Provider setup cannot be inferred
from a ChatGPT subscription or a successful synthetic fixture.
