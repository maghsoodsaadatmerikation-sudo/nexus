# Artifact 05 — HTTP Gateway Contract v0.1

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

## HTTP contract

`POST /v1/requests` accepts JSON with:

```json
{
  "request_id": "optional-client-id",
  "authority": "user",
  "action": "reflect",
  "subject": "opaque",
  "payload": "opaque"
}
```

A successfully delegated request returns `202 Accepted`:

```json
{
  "request_id": "...",
  "status": "pending"
}
```

`GET /v1/requests/{id}` returns the transport-visible request status or `404` when unknown.

## Authority invariant

HTTP is not an authority source. The gateway forwards the supplied envelope; constitutional authorization remains exclusively in the core delegate.

## Verification boundary

This artifact is developed from the immutable `prototype-0.1-verification-sealed` boundary. It does not modify that tag.
