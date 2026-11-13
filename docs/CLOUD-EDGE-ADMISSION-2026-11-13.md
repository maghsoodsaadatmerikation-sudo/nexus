# Cloud edge admission hardening — 13 November 2026

## Scope
The public FastAPI edge formerly bounded HTTPX's upstream connection pool to 32
connections, but accepted unlimited concurrent authenticated forwarding handlers
while they waited or consumed inbound request bodies. Slow authenticated senders
could occupy request memory and queues without a matching application admission
ceiling.

The edge now allocates a separate 32-slot non-queuing `anyio.CapacityLimiter`
for core forwarding. Authentication, secure core configuration, and decoded-path
checks occur before a slot is taken. A saturated pool rejects with HTTP 429 and
`Retry-After: 1` before reading request bytes. Slots are released on success,
upstream errors, oversized replies, request timeouts, and cancellation. The
existing four-slot model bridge has independent capacity.

## Boundaries
This is a single-process edge admission limit, **not** a distributed rate limit,
per-identity fairness control, credential validation, or protection from all DoS.
An authenticated slow body can hold one slot until the existing 30-second limit.
The upstream Rust gateway retains final authentication and constitutional policy.
No new paid resource or production deployment is part of this source change.

## Acceptance
`nexus-cloud/tests/test_core_admission.py` checks that saturation rejects
without reading a body, and that happy-path, upstream-failure, response-limit,
and unauthorized paths do not leak capacity. Existing transport contract and
complete cloud CI remain required.

## Production hold
The legacy Render `nexus` Docker service was directly observed on 13 November
2026 with `autoDeploy=yes`, trigger `commit`, branch `main`.
This patch stays on an isolated PR branch rather than triggering that service.
Do not merge until the operational auto-deploy/recovery boundary is controlled.
