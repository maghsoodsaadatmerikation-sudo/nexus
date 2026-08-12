# Artifact 05 — HTTP Gateway Boundary Contract

## Purpose

Artifact 05 is a transport boundary. It converts HTTP input into a `RequestEnvelope`, delegates that envelope to a constitutional boundary, and serializes the transport result.

The gateway does **not** own epistemic or policy authority.

## Allowed operations

```text
parse
validate_shape
envelope
delegate
serialize
```

## Forbidden operations in the gateway

```text
authorize
deny
interpret
execute
mutate_policy
```

The integration adapter may supply a `ConstitutionalDelegate`; the gateway library itself has no `PolicyEngine` or `Executor` dependency and cannot manufacture an `AuthorizedRequest`.

## HTTP contract

### POST /v1/requests

A syntactically valid request is delegated and returns:

```http
202 Accepted
```

Response shape:

```json
{
  "request_id": "r-05",
  "status": "pending"
}
```

`202` means the transport accepted the request for downstream processing. It does not assert that execution has completed.

### GET /v1/requests/{id}

Known request: `200 OK`.

Unknown request: `404 Not Found`.

### Invalid transport shape

Malformed JSON, invalid action shape, or an explicitly empty request ID is rejected at the transport boundary with `422 Unprocessable Entity`.

### Downstream delegate failure

If the constitutional delegate is unavailable, the gateway returns `502 Bad Gateway`.

The gateway does not convert that failure into a policy decision.

## Boundary proof

The contract tests cover:

- delegation without authorization;
- `202 Accepted` semantics;
- pending status retrieval;
- malformed action rejection;
- empty request-ID rejection;
- delegate failure translation;
- unknown request handling.

The CI workflow additionally rejects direct `PolicyEngine`, `Executor`, `.authorize()`, or `.execute()` references inside `artifact-05/src/lib.rs`.

## Authority invariant

HTTP is not an authority source. The gateway forwards the typed envelope; constitutional authorization remains exclusively in the core delegate.

## Verification rule

Prototype-0.2 must not replace or rewrite the sealed Prototype-0.1 tag. Changes are developed on `prototype-0.2-gateway-boundary` and must pass the Artifact 05 workflow before any merge or new seal is created.
