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

## Read-only public observer: fail-closed response validation

The independent `scripts/observe-pilot-runtime.py` performs only five public
HTTPS GETs, without bearer tokens, POST requests, redirects or production writes.
For `/livez` and `/readyz`, an HTTP 200 **alone is insufficient**:
each response must be bounded JSON with exactly the expected `status`
(`alive` or `ready`), `Content-Type: application/json` and
`Cache-Control: no-store`. Duplicate JSON properties, unexpected fields,
malformed bodies, oversized payloads and cacheable responses are blockers.
A valid `503 {"status":"quarantined"}` is recorded distinctly, but remains
unready. Anonymous 401 responses must also carry `no-store` to avoid
a false-green privacy/cache assessment. Runtime identity parsing rejects duplicate
properties and still compares only **self-reported** source metadata to the
expected hash; this is not independent binary attestation.

The strict observer has negative tests for fake 200 responses, conflicting
JSON, bad content type, oversized bodies, 503 quarantine and unsafe 401 caching.
These tests run in required PR verification and the dedicated observer-contract
workflow. They use synthetic responses. They do **not** establish public
availability, a working authenticated transaction, backup recovery,
operational release approval or Seal readiness. `public_checks: SATISFIED`
must never be interpreted as `promotion_ready`.
