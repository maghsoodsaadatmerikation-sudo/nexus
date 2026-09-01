# NEXUS Operational Observability Contract

This contract applies to post-v1.0 operational signals. Observability reports service state; it does not create epistemic authority.

## Allowed operational signals

NEXUS may emit coarse lifecycle information needed to operate the service, including:

- process startup;
- bind address;
- configured data-directory path;
- authentication configured/not configured state without the secret value;
- process/server exit errors;
- container health state.

## Prohibited log content

Operational logs must not intentionally emit:

- `NEXUS_API_TOKEN` or bearer authorization headers;
- question, claim, evidence, alternative, rationale, or judgment text;
- imported/exported workspace JSON;
- machine-analysis payloads;
- secrets or credentials from environment variables;
- a claim that service health implies epistemic correctness.

## Current lifecycle format

The executable emits a redacted startup signal of the form:

```text
NEXUS_OP event=startup bind_addr=<socket> data_dir=<path> auth=configured
```

On an Axum server error after startup it emits:

```text
NEXUS_OP event=server_exit error=<operational error>
```

The token value is never included.

## Interpretation boundary

A `healthy` container or a successful startup event means only that the process is operational enough to answer its liveness contract. It does not mean that any claim, judgment, evidence item, or model output is true, justified, or authorized.

Operational state therefore carries no additional epistemic authority.

## Retention and redaction

Operators should retain only the minimum lifecycle logs needed for service diagnosis. If a hosting platform adds request logging, authorization headers and request/response bodies must be disabled or redacted where configurable. NEXUS application code should not add evidence-bearing payload logging for convenience.

## Verification

CI must observe the redacted startup marker from the production-shaped container and continue to verify container health, authenticated backup/recovery, and durable restart. Verification evidence may record that the observability check passed, but must not capture the bearer token as evidence.
