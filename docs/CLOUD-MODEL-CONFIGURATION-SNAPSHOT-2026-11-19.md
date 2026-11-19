# Studio configuration snapshot architecture (2026-11-19)

## Structural contract

The optional model bridge is a non-authoritative FastAPI transport. It never owns constitutional execution rights. The Rust core still controls those rights.

Previously, Studio validated the model endpoint, model ID and Studio token together, but re-read the model adapter and upstream API key later in the same request. A configuration rotation during request processing could mix fields from different configurations.

The new `model_configuration.py` validates and freezes the endpoint, model ID, adapter, Studio token, upstream API key and provider host in one `ModelConfig`. The request uses that one snapshot to verify authentication, validate the reviewed configuration ID, select provider-specific payload fields, connect to the provider and label the result.

The system policy is likewise captured at request start and used for both the review fingerprint and the actual system message.

## Review continuity and migration

The configuration ID now includes a digest of the system policy alongside provider endpoint, model ID and adapter. Changing any reviewed behavior invalidates stale consent with HTTP 409. Secrets do not appear in the ID or the status response. Secret rotation alone does not invalidate consent, while each in-flight request uses its original admitted secret snapshot.

Because the fingerprint includes the policy for the first time, previously reviewed Studio sessions must fetch status and review the new configuration once after rollout.

## Verification

`nexus-cloud/tests/test_model_configuration.py` verifies immutable configuration, secret redaction from object representation, policy-change invalidation, no mid-request environment mixing and new-request review enforcement. Existing cloud adapter suites continue to test transport admission, capacity release, authorization, and non-authoritative response semantics.

CI: `.github/workflows/cloud-adapter.yml` runs locked cloud tests whenever `nexus-cloud/**` changes.

This change does not establish a public deployment, provider quality, durable-host resilience, or Stage D verification.
