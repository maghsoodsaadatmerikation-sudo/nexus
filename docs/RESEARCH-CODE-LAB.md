# Research and local code/data lab

Added to NEXUS Studio on 13 November 2026. These tools do not require a model
provider, a provider API key, a new server, or an additional hosted plan.
They do not establish ChatGPT model/reasoning parity.

## Public source retrieval

The research desk makes a direct, explicit, unauthenticated CORS GET request to
one of two fixed API providers:

- Wikipedia Action API: an introduction excerpt, title, page identity and link.
  The interface supports English, Persian, Spanish, French, German and Arabic.
- Crossref REST API: a title, bounded author list, publication year, DOI and work
  type. This is bibliographic metadata; no paper findings or full text are read.

The exact standalone query is at most 250 characters. No conversation, project
memory, file, API token or document is added to it automatically. Changing the
query/provider/language revokes approval. Requests omit credentials and referrers,
reject redirects, have a 20-second waiting deadline and stop after 160,000 bytes.
At most five source cards are displayed. Unavailable providers/CORS/network
failures are reported; no results or AI answer are fabricated as a fallback.
There is no promise that every provider works in every country/network/browser.

Source cards render as inert text. Links open only on user navigation, with
noopener/noreferrer. Keeping an excerpt as a project source is a separate action:
it retains the provider URL, query, retrieval timestamp, kind and attribution.
The existing encrypted project archive can then retain that source if explicitly
saved. These records are source leads, not independent verification, immutable
web snapshots, clinical evidence appraisal or automated research conclusions.
Wikipedia attribution terms remain applicable; a DOI does not grant access to
copyrighted article text.

## Local JavaScript execution

The lab accepts a JavaScript function body and a separate input string. Execution
requires the exact code/input checkbox to be approved after edits. The program
can use `input`, `console.log` and `return`. Nothing runs merely because a model
response, file or source passage contains code. Nothing is uploaded for execution.

The trusted runner creates a hidden iframe with `sandbox="allow-scripts"` and
without `allow-same-origin`. This creates an opaque origin. A fixed, restrictive
CSP is installed before any script; user code is sent as a message after a
nonce-bound ready handshake. It is parsed only inside a Blob dedicated Worker,
never as HTML or as code in the Studio document. That Worker inherits the iframe
CSP: network is denied and external scripts/eval are not enabled. Archive/storage
access is denied by the opaque origin. Child workers, shared workers and broadcast
channels are disabled. The parent accepts only bounded log/result/error text from
the exact frame with its job nonce and opaque origin.

Limits:

| Resource | Bound |
| --- | --- |
| Code | 100,000 UTF-8 bytes |
| Input | 262,144 UTF-8 bytes |
| Execution waiting time after ready | 3 seconds |
| Startup waiting time | 6 seconds |
| Output | 64,000 UTF-8 bytes, with bounded message count |
| Host process / filesystem | Not exposed to the worker |
| Network | Blocked by the sandbox document/worker CSP |
| Memory | **No hard allocation quota**; this is a browser worker, not an OS sandbox |

Stop, a project change, edits and locking invalidate pending results. Completion,
error, cancel or timeout remove the execution context. Output is untrusted data,
not an action receipt, verified fact or human judgment. Inputs/results are session
only; a user can copy output into the writing canvas and explicitly save a version.
Locking clears input/output fields and chart pixels. This is JavaScript execution,
not Python, a shell, package installation, access to a user's computer, a remote
agent, or a guarantee against browser vulnerabilities/resource exhaustion.

## Charts

A separate local Canvas renderer accepts only validated JSON data:

```json
{"type":"bar","title":"Example","labels":["A","B","C"],"values":[3,5,2]}
```

Supported types: `bar` and `line`. Labels and values must have matching lengths,
from one to 200 points; each value must be finite and within ±10^12. Rendering is
not code evaluation. Negative and zero values are supported. Labels are sampled
and shortened for readability; exact data remain in the JSON input. PNG export
is explicit and may reveal private labels/data. The lab does not infer statistical
significance or causation and does not make scientific validation claims.

## Verification

- 40 existing Studio state/encryption checks remain passing locally.
- 31 new parser, query, transport-privacy, source-shape and chart checks pass.
- Real Wikipedia and Crossref HTTPS responses were parsed during development:
  five source leads each; both returned CORS `*`. This is a point-in-time provider
  availability observation, not an uptime guarantee or a full research-quality test.
- Real Chromium narrow/wide acceptance exercises the actual worker, checks opaque
  origin and storage denial, compares a live local sentinel control request with
  a sandbox fetch attempt, terminates an infinite loop, rejects excessive output,
  verifies recovery after failed jobs, draws actual chart pixels and clears on lock.
  The sentinel must receive only the parent control request, never sandbox traffic.
- Browser research UI uses explicit synthetic API fixtures for deterministic
  consent/race/provenance tests; those fixtures are not labeled live source tests.
- No actual model, OS/Python sandbox, physical Android audio/permissions, image
  generation, unattended scheduler or external app OAuth is established by this work.

## Primary technical references

- https://www.mediawiki.org/wiki/API:Cross-site_requests
- https://www.mediawiki.org/wiki/Extension:TextExtracts#API
- https://github.com/CrossRef/rest-api-doc
- https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy
- https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/sandbox
