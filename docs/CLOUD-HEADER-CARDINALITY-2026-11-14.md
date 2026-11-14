# Reject ambiguous HTTP headers at the core proxy — 14 November 2026

## Observed gap
The public FastAPI `/v1/{path}` transport selected one value via
`request.headers.get("authorization")`, `get("content-length")`,
`get("content-type")` and `get("content-encoding")`.
Clients may send repeated header fields, while downstream proxies,
middleware and servers can select or combine different occurrences.

A duplicate `Authorization` field can be interpreted inconsistently
across hops. Conflicting `Content-Length` or media/encoding declarations
can cause different interpretations of a request's framing or content.

## Source repair
- Require exactly one `Authorization` field for opaque core delegation.
  Duplicate credentials (including identical copies) produce HTTP 400;
  a single malformed/missing bearer remains HTTP 401.
- Permit zero or one of each `Content-Length`, `Content-Type` and
  `Content-Encoding` headers. Duplicates fail with HTTP 400, before
  polling the body or contacting the private core.
- Preserve existing 1 MiB bounded body, response limit, deadline, capacity,
  HTTPS-only origin, no redirect, raw-body fidelity and pass-through status.
- Add isolated regression tests using actual FastAPI TestClient and a
  constructed ASGI request whose `receive` function must never be polled.

## Limits
This is defense in depth; a front HTTP proxy must still reject invalid
wire framing and protect against request smuggling. This change does not
replace transport authentication, gateway authorization, rate limiting or
complete production threat modeling. It is distinct from optional Studio
model JSON hardening in PR #195.

Do not merge or deploy this draft without passing its exact-head CI and
resolving documented production freeze/restore and main ruleset blockers.
No production data, hosted service settings, release tags, evidence seals
or existing workspaces are modified by the draft.
