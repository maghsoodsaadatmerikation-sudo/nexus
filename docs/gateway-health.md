# Gateway liveness and admission readiness

Status: DEVELOPMENT / UNSEALED

| Probe | HTTP response | Meaning |
| --- | --- | --- |
| GET /livez | 200, `{"status":"alive"}` | Listener/router responds |
| GET /readyz | 200, `{"status":"ready"}` | Startup recovery quarantine is absent |
| GET /readyz | 503, `{"status":"quarantined"}` | Recovery quarantine still blocks all mutations |

HEAD preserves the corresponding status and headers with no response body.
Both routes are public, bounded, and return `Cache-Control: no-store`. They expose
no bearer token, workspace/request identifiers, filesystem paths or release claims.
Probes do not consume request admission/rate budgets, write storage, delegate work,
clear quarantine, or construct AuthorizedRequest. The workspace/request APIs retain
their transport authentication and constitutional authorization boundaries.

Readiness reads the same startup-latched flag used by the mutation middleware.
A restored volume remains alive while not ready. Restart with the marker still
present remains not ready. Removing the marker from a running process does not
change its readiness; the explicit offline replay-risk acknowledgment and gateway
restart remain necessary. See [full-data recovery](full-data-recovery.md).

## Automated checks

```bash
# A readiness monitor must treat any non-200 result or connection failure as unavailable.
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:3000/readyz
```

The Docker HEALTHCHECK uses `/livez`: quarantine must not create a restart loop.
Traffic admission monitoring should check `/readyz` separately. The current Render
Blueprint's root health path is a liveness/UI check; it does not establish this new
admission-readiness condition. Repository verification of these routes does not
prove a deployed provider's routing configuration.

Readiness is deliberately limited to the recovery gate. A 200 response is not a
promise that a subsequent request will pass auth, policy, rate/capacity limits,
filesystem operations or execution. It does not probe disk writability, measure
throughput, establish production availability, validate a recovery point, confer
authority, or constitute attestation/Seal readiness. In particular, `pending` status
still records acceptance rather than durable completion.

CI checks public liveness/readiness and no-store headers on the real HTTP listener
through quarantine, restart, explicit resumption and another restart. HTTP tests
also check HEAD, token-independent minimal responses, zero delegate/store changes,
rate-budget preservation and readiness remaining latched after marker removal.
The static resilience contract fails closed if the routes, Docker liveness path or
503 quarantine witness are removed. Current executed evidence is required for PASS.

`A_out ≤ A_in`, evidence ≠ authority, the AuthorizedRequest boundary, CT-001..020,
Bootstrap versus Verify separation and both pinned Cargo.lock files still apply.
