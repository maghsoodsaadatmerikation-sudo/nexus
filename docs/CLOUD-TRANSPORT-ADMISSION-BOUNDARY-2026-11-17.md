# Cloud request admission boundary (2026-11-17)

## Scope

The FastAPI adapter is a **transport**, not a constitutional policy authority.
The Rust gateway remains the sole evaluator of delegated actions; the optional
Studio model bridge returns drafts, not decisions. This change makes the same
request-body framing checks apply at both independently authenticated edges.

## Trust and resource boundaries

- The delegated `/v1/*` edge requires **exactly one** nonempty Bearer header;
  the Studio `/studio-api/respond` edge requires exactly one credential whose
  bytes match the operator-configured token.
- Both edges call `transport_bounds.read_bounded_body` **after admission** and
  before any upstream request. The helper rejects repeated Content-Length,
  the simultaneous presence of Content-Length and Transfer-Encoding, malformed
  decimal lengths, declared size above the route cap, streamed bytes above the
  route cap, and declared/observed length disagreement.
- The helper enforces one total body-read deadline even when chunks arrive
  slowly, without trusting a Content-Length header. Cancellation and network
  disconnects propagate; caller-owned capacity limiters release in `finally`.
- Route-specific public limits remain unchanged: 1 MiB for opaque core request
  bodies and 96,000 bytes for Studio model context. The core uses HTTP 408 for a
  body deadline; the Studio model uses HTTP 504.
- Studio accepts `application/json` and its parameterized form, such as
  `application/json; charset=utf-8`, but not prefix lookalikes or duplicate
  Content-Type. Model consent, server policy, credentials, and output validation
  remain unchanged.
- Transport header rejection does **not** certify the caller as an authorized
  human or attest to upstream integrity. Existing audit, revocation and
  production-promotion boundaries remain in force.

## Regression gate

Run:

```bash
cd nexus-cloud
uv sync --locked --group dev
uv run pytest -q tests/test_admission_shared.py tests/test_transport_bounds.py \
  tests/test_gateway_capacity.py tests/test_studio_model.py
```

GitHub's `NEXUS Cloud Adapter Verification` path-filtered workflow exercises
the whole cloud adapter test suite for this change. The PR-wide verification
and any independent public-browser witness are separate checks. The unresolved
real-public offline Service Worker issue (#260, investigation PR #269) is **not**
resolved by a cloud transport refactor, nor does a green unit test authorize
Render/Railway publication.
