# Stage D legacy operator: bearer transport containment

Status: engineering hardening only. No provider deployment, production data
access, real restore or release authorization is established by this PR.

## Concrete defect

The historical `ops/stage_d_operator.py` used
`urllib.request.urlopen(Request(..., headers={"authorization": "Bearer ..."}))`
for authenticated Stage D operations. Python's default HTTP redirect handler
can construct a new request by copying an existing Authorization header, even
for a different redirect destination. It also follows proxy environment
settings and previously loaded unbounded response bodies. A wrong origin,
redirect, proxy or unexpectedly large response could expose an operator bearer
or prevent reliable evidence processing.

## Implemented boundary

- `ops/stage_d_transport.py` validates the HTTPS origin before building a
  request. No URL credentials, nonstandard ports, paths, query or fragments.
- The request route is limited to GET /, GET /v1/workspaces/{id},
  POST /v1/workspaces and POST /v1/workspaces/import. No other method,
  query string or cross-origin destination is accepted.
- `urllib.request.ProxyHandler({})` prevents using ambient proxy settings;
  `NoRedirect` prohibits all 30x redirects. A 30x status is an error, not
  evidence of successful API access. No bearer is passed in subprocess argv.
- Request JSON is bounded and non-finite numeric values are rejected. Response
  size is limited to 2 MiB, timeout to 10 seconds, and ambiguous Content-Length
  fields are rejected.
- Private responses must be non-cacheable application/json objects without
  duplicate properties, including 401 and 404 errors. Malformed responses
  fail closed rather than being treated as a valid Stage D phase.
- The legacy `ops/stage_d_operator.py` delegates to this transport; the
  operator Dockerfile now includes the new helper.

## Acceptance evidence

The synthetic `scripts/test-stage-d-operator-transport.py` tests origin
validation, same-origin path restrictions, credential header handling,
redirect rejection, no ambient proxies, bounded responses, duplicate JSON,
invalid content type and cacheability, HTTP 401, invalid writes and defensive
integration wiring. The dedicated unprivileged workflow and primary PR check
run it on the exact candidate; neither uses actual operator tokens or
provider endpoints.

## Safety limits and outstanding items

This protects **HTTP transport**, not all operator-side filesystem evidence
writes. The separate draft PR #171 works on the newer Stage D shell evidence
collector's filesystem and evidence-hygiene boundaries. These changes are
independent and must be reconciled before any future integration.

The tests do not prove production HTTPS liveness, full-volume backups,
persistent storage, independent offsite encrypted restore, or a release.
Provider configuration remains blocked by #154 (Render auto-deploy) and
#168 (strict GitHub required-check freshness). Keep this PR a draft. No
changes to main or installed operator deployments are authorized.

`A_out <= A_in`; test evidence is not production or human release authority.
