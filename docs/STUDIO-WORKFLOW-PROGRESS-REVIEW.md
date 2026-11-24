# Workflow progress review (stateless API candidate)

The authenticated POST /studio/api/workflow/progress accepts the exact original Plan, its SHA-256 from /studio/api/workflow/review, a list of acknowledged step IDs, and an optional cancelled boolean. Maximum request body 32 KiB; the existing plan limits remain unchanged.

The server recomputes the plan identity, rejects changed plans, unknown/duplicate acknowledgments, and acknowledgments without all prerequisites. It returns deterministic review-ready and blocked steps, counts, cancellation projection, and caller_reported_only evidence. No step is dispatched. Acknowledgment does not establish that a human performed or approved an operation; the endpoint receives client claims, not independently verified receipts. Cancellation is only a projection of the supplied flag, not a durable stop signal.

Every response has execution_authorized=false. No tool calls, external writes, durable jobs, saved progress, workflow token, real execution or Studio UI integration are introduced. The server is stateless: a later request may submit a different valid history. A future durable runner needs authenticated per-user ownership, append-only transitions, idempotency, independently bound approval, cancellation and recovery.

Validation uses the existing operator token and bounded request reader. Successful and validation-error responses are no-store. Existing review behavior is preserved. See nexus-cloud/tests/test_studio_workflow.py for proposed regression cases; real deployment and CI are separate gates.
