# Gateway liveness and admission readiness

Status: DEVELOPMENT / UNSEALED

| Probe | HTTP response | Meaning |
| --- | --- | --- |
| GET /livez | 200, `{"status":"alive"}` | Listener/router responds |
| GET /readyz | 200, `{"status":"ready"}` | Startup recovery quarantine is absent and the pinned request ledger is presently reachable (if configured) |
| GET /readyz | 503, `{"status":"quarantined"}` | Recovery quarantine still blocks all mutations |
| GET /readyz | 503, `{"status":"storage_unavailable"}` | Configured request ledger is missing, inaccessible or replaced after startup |

HEAD preserves the corresponding status and headers with no response body.
Both routes are public, bounded, and return `Cache-Control: no-store`. They expose
no bearer token, workspace/request identifiers, filesystem paths or release claims.
Probes do not consume request admission/rate budgets, write storage, delegate work,
clear quarantine, or construct AuthorizedRequest. The workspace/request APIs retain
their transport authentication and constitutional authorization boundaries.

Readiness reads the same startup-latched flag used by the mutation middleware,
and checks the pinned durable request ledger's path identity and read-only
directory enumeration whenever a ledger is configured. Moving, replacing or
making that ledger inaccessible changes /readyz to 503 on the next probe,
while /livez remains 200. Restoring the *original* pinned ledger directory
recovers /readyz without a restart. No HTTP probe is allowed to create a
marker, mutate data, consume request budget or clear the replay-risk latch.
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

Readiness covers the startup recovery gate and the currently accessible,
pinned request-ledger directory. A 200 response is not a promise that
the next request will pass auth, policy, rate/capacity limits, filesystem
operations or execution. The check does **not** write to storage, detect
ENOSPC/disk exhaustion, inspect the workspace repository or independently
validate full-volume recoverability. It does not measure throughput, establish
production availability, validate a recovery point, confer authority, or
constitute attestation/Seal readiness. In particular, `pending` status still
records acceptance rather than durable completion.

CI checks public liveness/readiness and no-store headers on the real HTTP listener
through quarantine, restart, explicit resumption and another restart. HTTP tests
also check HEAD, token-independent minimal responses, zero delegate/store changes,
rate-budget preservation and readiness remaining latched after marker removal.
The static resilience contract fails closed if the routes, Docker liveness path or
503 quarantine witness are removed. Current executed evidence is required for PASS.

`A_out ≤ A_in`, evidence ≠ authority, the AuthorizedRequest boundary, CT-001..020,
Bootstrap versus Verify separation and both pinned Cargo.lock files still apply.


## Container health command

Docker executes `/usr/local/bin/nexus --health-check` directly. The probe reads
`NEXUS_BIND_ADDR`, preserves its configured port, and maps wildcard IPv4/IPv6 binds
to the matching loopback address. It requires an HTTP 200 response from `/livez`
with exactly the bounded `{"status":"alive"}` JSON schema, a single consistent
Content-Length and no transfer-encoding ambiguity. It rejects redirects, misleading
error bodies, duplicate JSON fields, readiness payloads and oversized responses.
Connect/write/read operations have bounded timeouts and a two-second overall
budget. The supported probe profile is the gateway's non-chunked JSON response
with connection close. Port zero is not a discoverable container health endpoint.

The health command runs before token/storage initialization, sends no bearer or
proxy credentials, does not follow redirects and creates no gateway data. It
reports success/failure only through its exit status. Health remains liveness:
recovery quarantine still returns `/livez` 200 and `/readyz` 503. The CI witness
checks Docker's actual health engine on default/custom ports and a quarantined
isolated container, plus a compiled-CLI witness against controlled HTTP failures.
