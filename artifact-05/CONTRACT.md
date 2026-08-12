# Artifact 05 — HTTP Gateway Contract v0.1

## Purpose

Artifact 05 exposes the Constitutional Core through HTTP without creating a second authority layer.

## Boundary

The HTTP layer MAY:

- parse HTTP requests;
- validate required request shape through typed deserialization;
- construct `RequestEnvelope`;
- delegate the envelope to the Constitutional Core boundary;
- serialize transport responses.

The HTTP layer MUST NOT:

- authorize;
- deny;
- interpret payload meaning;
- execute constitutional actions;
- mutate policy;
- increase authority.

## HTTP contract

`POST /v1/requests` accepts the typed envelope shape below. `action` is a tagged core action: its required companion field depends on the action variant.

Reflect example:

```json
{
  "request_id": "optional-client-id",
  "authority": "user",
  "action": "reflect",
  "subject": "opaque",
  "payload": "opaque"
}
```

Present example:

```json
{
  "request_id": "optional-client-id",
  "authority": "user",
  "action": "present",
  "value": "opaque",
  "payload": "opaque"
}
```

Select example:

```json
{
  "request_id": "optional-client-id",
  "authority": "user",
  "action": "select",
  "option": "opaque",
  "payload": "opaque"
}
```

A successfully delegated request returns `202 Accepted` and is represented as `pending` at the transport boundary:

```json
{
  "request_id": "...",
  "status": "pending"
}
```

Malformed JSON or a malformed action shape is rejected by the HTTP extractor with `422 Unprocessable Entity`; it never reaches the constitutional delegate.

`GET /v1/requests/{id}` returns the transport-visible request status or `404` when unknown.

## Authority invariant

HTTP is not an authority source. The gateway forwards the typed envelope; constitutional authorization remains exclusively in the core delegate.

## Verification boundary

This artifact is developed from the immutable `prototype-0.1-verification-sealed` boundary. It does not modify that tag.
