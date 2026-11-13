# NEXUS Cloud Adapter

This FastAPI service is a deliberately non-authoritative transport adapter in
front of the NEXUS Rust gateway. It requires a syntactically non-empty bearer
credential, forwards that credential and the opaque `/v1/*` request to the
constitutional core, and preserves upstream HTTP status codes—including the
`202 Accepted` / `pending` request contract.

The adapter does **not** establish that a credential is valid and does **not**
authorize actions, interpret evidence, create human judgments, execute
constitutional actions, mutate policy, or persist NEXUS workspace state.
Authentication decisions and all constitutional authority remain in the Rust
core.

## Configuration

- `NEXUS_CORE_URL` (required for `/v1/*`): HTTPS origin of the deployed Rust
  gateway, for example `https://core.example`. A trailing slash is normalized.
  User-info credentials, path prefixes, query strings, fragments, malformed
  ports, and non-HTTPS schemes are rejected fail-closed.

The caller's `Authorization: Bearer ...` header is passed through to the Rust
gateway; tokens are not stored by this adapter. The HTTP client is created with
`trust_env=False`, so ambient proxy environment variables are not inherited by
the adapter's upstream client.

## Verification

The adapter has two deliberately separate verification layers:

1. `.github/workflows/cloud-adapter.yml` is a read-only contract workflow for
   pushes and pull requests. It pins the setup action and `uv` version, installs
   Python 3.13, syncs strictly from `uv.lock`, compiles the Python sources, and
   runs the transport contract tests.
2. `.github/workflows/cloud-adapter-evidence.yml` runs only on `main` pushes or
   explicit dispatch. It repeats the frozen contract verification, generates a
   self-audited manifest bound to the exact commit, hashes the source, tests,
   lockfile, and both cloud workflows, bundles that evidence, creates a GitHub
   artifact attestation for the bundle, and uploads the bundle plus checksum.

The evidence manifest states its scope explicitly: `Authority Claim: NONE`,
`Epistemic Claim: TRANSPORT-CONTRACT-ONLY`, and `Stage D Claim: NOT SATISFIED`.
A successful cloud-adapter attestation therefore proves only that the named
commit passed this transport contract. It does **not** elevate the adapter into
an authority-bearing component and does **not** satisfy the v1.1 Stage D
durable-production evidence requirement.

For local verification:

```sh
uv sync --frozen
uv run --frozen pytest
```

## Local development

```sh
uv sync --locked
uv run fastapi dev
```

Operational liveness is available at `/healthz`. A successful health response
is not evidence of epistemic correctness or constitutional authorization.

## Deploy to FastAPI Cloud

Sign up and log in at FastAPI Cloud, then deploy with:

```bash
uv run fastapi deploy
```

Deployment of this adapter is only deployment of a transport edge. The Rust
constitutional core must remain separately deployed and must be configured as
the secure upstream through `NEXUS_CORE_URL`.

## Project structure

- `main.py` - non-authoritative FastAPI transport adapter
- `tests/test_contract.py` - transport-boundary contract tests
- `pyproject.toml` / `uv.lock` - locked Python environment

## Optional Studio model bridge

This adapter also exposes `/studio-api/status` and `/studio-api/respond`. Model
use is disabled unless `NEXUS_MODEL_URL`, `NEXUS_MODEL_ID` and the separate
`NEXUS_STUDIO_TOKEN` are configured by the operator. The optional provider key
`NEXUS_MODEL_API_KEY` remains on the server. The endpoint accepts only reviewed
text messages and has no tools. See [Studio setup and limits](../docs/STUDIO-CAPABILITIES.md).

Deploy from the repository root to include the optional `/studio` HTML page.
A gateway-only deployment may use an explicitly configured `NEXUS_STUDIO_ORIGIN`
with Studio hosted separately. There is no provisioned model or live provider
quality test in this repository's synthetic acceptance suite.

## Operational readiness and model dispatch budgets

- `GET /healthz` reports **adapter liveness only**.
- `GET /core-readyz` returns 200 only after a credential-free, no-redirect,
  byte-capped (512 B), 2-second probe sees HTTP 200 and `{"status":"ready"}`
  from the configured Rust gateway's `/readyz`. Otherwise it returns a
  generic, no-store 503. Two non-queuing probe slots isolate this route from
  delegated traffic. It does not establish persisted-data recovery or validate
  constitutional authority. The Rust readiness endpoint retains its own
  documented limited scope.
- Delegated API requests have 32 non-queuing core slots, separate from probe
  and optional model slots. The adapter rejects saturation before body reading.
- `NEXUS_MODEL_MAX_CALLS_PER_HOUR`: positive integer, default 60, max 1,000,000.
- `NEXUS_MODEL_OUTPUT_TOKENS_PER_HOUR`: positive integer, default 131,072,
  max 100,000,000. It reserves the **requested maximum output tokens** before
  dispatch, not the eventual token usage. Invalid operator settings fail closed.
  An exhausted budget responds HTTP 429 with `Retry-After`.
- `NEXUS_MODEL_INPUT_BYTES_PER_HOUR`: positive integer, default 1,048,576,
  max 100,000,000. Counts request-body bytes plus the model policy bytes as
  a conservative approximation to submitted input; it is not a token count.
- The model budget is **per process**, reset by restart, and counts attempts
  that may have reached the provider even when they fail or time out. It does
  not include input tokens, prices, retries outside NEXUS or other replicas.
  Configure hard spending limits and monitoring at the provider as well.
