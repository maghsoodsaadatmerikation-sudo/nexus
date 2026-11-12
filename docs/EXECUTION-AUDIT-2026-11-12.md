# Execution-path audit and repairs

Development candidate based on infrastructure PR #129, head
`8afc61c70dc8dd0c6c27166219228afd2022ca72`.
No production deployment or release seal is claimed.

## Reproduced defects

Five new HTTP regressions all failed against the infrastructure candidate:
workspace mutations bypassed the configured body cap and shared rate budget;
ephemeral submission accepted invalid IDs; readiness falsely stayed ready after
ledger replacement; and workspace forms silently ignored unknown fields.

Repairs:

- Apply the configured body cap to all six workspace mutation routes, before
  extractors/delegates. Explicit limits above Axum's default also work.
- Share one existing rate budget between workspace writes and submission.
  Authenticate and enforce quarantine first; enforce rate before polling bodies.
  Authenticated malformed/oversized/timed-out attempts consume this budget too.
- Bound body ingestion to 15 seconds by default. The executable accepts positive
  `NEXUS_BODY_READ_TIMEOUT_SECONDS`; library callers can set the same deadline.
  Timeout returns HTTP 408 `request_body_timeout` without request reservation or
  delegation. This timeout never cancels an already-started delegate operation.
- Reject empty/whitespace-only or over-100-byte IDs for submission in both durable
  and ephemeral modes; apply the same bound to workspace IDs, routes and supplied
  claim/alternative IDs. Generated UUIDs continue to work.
- Reject unknown fields in create, claim, alternative and judgment form DTOs,
  including the tagged claim-origin form. Snapshot/analysis schemas are unchanged.
- Move synchronous submission, ledger writes, workspace operations, rate-lock waits
  and readiness filesystem checks off the asynchronous network worker. A shared
  32-slot execution gate bounds submission and workspace delegates (positive
  `NEXUS_MAX_CONCURRENT_EXECUTIONS` overrides the default). Capacity rejection is
  HTTP 503 before reservation/delegation. A permit remains owned by started work
  if the HTTP client disconnects; no cancellation or automatic re-execution is
  claimed. Worker failures are redacted rather than propagating a panic to HTTP.
- Report a missing/replaced ledger as HTTP 503 readiness while maintaining
  liveness. The synthetic real-listener outage witness checks repair/restart too.

Eleven HTTP tests cover these repairs, including never-completing bodies, bodies
that panic if polled after rate rejection, both directions of shared admission,
every workspace mutation path, configured body limits above 2 MiB, liveness on a single-thread runtime while a
synchronous delegate is deliberately blocked, and shared execution capacity held
through a client disconnect.
The complete gateway suite passes locally (65 passed; existing privileged
capacity witness is run separately by CI). Core authority checks remain required.

## What the executable capabilities actually do

| Capability | Implemented behavior | Boundary |
| --- | --- | --- |
| Request admission | Authenticate, bound input, reserve durable ID, delegate and retain acceptance/uncertainty | `pending` is acceptance, not proof of completion; no autonomous external actuator |
| Workspaces | Create/import/read, append evidence/alternatives/analysis and explicitly record human judgment | Single coordinated writer, private host directories and independent backups still required |
| Offline analysis | Bounded deterministic local data operations | No unrestricted code execution or inferred human judgment |
| Internet research | Consent-gated external search handoff | Search engines/results are not automatically ingested by a server agent |
| Conversation | Bounded, local guided dialogue and explicit draft transfer | No generative LLM or remote human peer |
| Files | Bounded import/preview and documented export packages | Arbitrary file execution and universal format conversion are not implemented |
| Voice | Opt-in browser speech adapters | Real-device microphone/speaker support still requires physical-device acceptance |

These missing general-purpose capabilities are product boundaries, not functions
that can be certified as present by renaming a button or returning HTTP 202.
The repair does not add external authority, paid infrastructure or a remote model.

## Integration and residual limits

This candidate depends on PR #129. Its integration hold remains: legacy Render
backend auto-deploys on `main`; fresh independently recoverable production-volume
evidence is absent. No source pin, volume, provider setting or release gate changes.

Rate limits are process-local and shared by the configured transport, not per-user
identity or distributed quotas. Readiness does not measure free space, fsync
durability, workspace-store health, authentication, executor outcomes or capacity.
Blocking delegates can still occupy the bounded blocking pool; a body deadline
is not an executor deadline. A stalled delegate is never blindly retried. Host/network connection limits and actual
production recovery remain separate acceptance work.
