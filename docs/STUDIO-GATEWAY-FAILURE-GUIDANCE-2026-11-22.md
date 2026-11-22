# NEXUS Studio — clear gateway failure guidance (22 November 2026)

## Problem

A user who explicitly reviewed and approved an AI model request previously
saw a generic failure notice for many different server, connectivity and
provider errors. This can lead to unnecessary manual retries, accidentally
repeated provider usage, or confusion about whether the last request was saved.

## Changes

The review and send path now maps **only fixed, local error classes** to
readable English and Persian messages:

| Condition | User guidance |
|---|---|
| HTTP 401/403 | Check NEXUS gateway access token and permissions |
| HTTP 409 | Recheck gateway model configuration and explicitly review again |
| HTTP 415/422 | Check selected model, execution mode and reviewed context |
| HTTP 429 | Check whether local budget was exhausted or gateway is busy |
| HTTP 503 | Inspect gateway/provider availability |
| HTTP 408/500/502/504 | Explain upstream failure and possible attempt usage |
| Other HTTP error | Report a generic gateway rejection |
| Network/CORS TypeError | Check gateway URL, connectivity and browser access |
| AbortError or local request deadline | Explain timeout without claiming no provider contact |
| Invalid JSON, malformed stream, invalid origin or response envelope | Refuse the answer; explain malformed response |

Crucially, **untrusted provider error text, URLs, credentials, response bodies
and arbitrary exception messages are not shown to the user**. No remote
error detail becomes an instruction. For uncertain network/timeout/upstream
errors, messages explicitly avoid claiming the request was not billed or
that the provider was never contacted.

**No automatic retries** are introduced, and a failed response is never
committed to the conversation tree. The unsent draft remains in the tab.
Reattempting any remote model request still requires a new explicit
exact-context review and consent. Existing model-slot validation,
separate privacy-warning consent and operator-only readiness behavior
remain enforced.

The streaming gateway path now preserves a non-2xx HTTP status before
validating the streaming content type, so an HTTP 429 is reported as
a busy/budget condition rather than an unexplained streaming-format error.

## Acceptance

```sh
node scripts/test-studio-core.mjs
python3 scripts/build-studio.py --check
python3 scripts/build-studio-static.py --check
python3 scripts/test-studio-gateway-errors-browser.py
```

The new isolated, real-Chromium witness runs against synthetic network
responses, not real providers; checks 401/403/409/415/422/429/503/502/504/404,
a disconnected transport, an AbortError, malformed buffered and streaming
responses, bilingual explanations, fixed route review, preserved drafts,
and exactly one sent request per explicit approval. Browser rendering and
static files are checked with a strict 635,000-byte HTML ceiling and a
SHA-256-pinned offline service worker.

## Release boundary

This is a **UI reliability and honesty improvement**, not an availability
guarantee, reimbursement mechanism, live provider authentication, deployment
or public endpoint test. No real provider credentials, paid tokens, user
conversations or live provider calls are used in its tests.
