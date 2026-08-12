# Artifact 05 — HTTP Gateway Contract v0.2

## Purpose

Artifact 05 exposes the Constitutional Core through HTTP without creating a second authority layer.

## Boundary

The gateway MAY:

- parse HTTP requests;
- validate request shape;
- construct `RequestEnvelope`;
- delegate the envelope to the Constitutional Core boundary;
- serialize transport responses.

The gateway MUST NOT:

- authorize;
- deny;
- interpret payload meaning;
- execute constitutional actions;
- mutate policy;
- increase authority.

The gateway's `authority` field is transport input only. Converting its wire representation to the core `Authority` type is not authorization and MUST NOT elevate the supplied value.

## HTTP contract

`POST /v1/requests` accepts JSON with this wire shape:

```json
{
  "request_id": "optional-client-id",
  "authority": "user",
  "action": "reflect",
  "subject": "opaque",
  "payload": "opaque"
}
```

For `present`, use `value` instead of `subject`; for `select`, use `option` instead of `subject`.

The gateway validates only that the fields required by the selected action are present. Unknown actions or missing action-specific fields are rejected with `400 Bad Request` before delegation.

A successfully delegated request returns `202 Accepted`:

```json
{
  "request_id": "...",
  "status": "pending"
}
```

A delegate failure returns `502 Bad Gateway`.

`GET /v1/requests/{id}` returns the transport-visible request status or `404 Not Found` when unknown.

## Authority invariant

HTTP is not an authority source. The gateway forwards the supplied envelope; constitutional authorization remains exclusively in the core delegate.

## Verification boundary

Prototype-0.2 is developed from the immutable Prototype-0.1 sealed boundary. The sealed Prototype-0.1 tag is never modified.
