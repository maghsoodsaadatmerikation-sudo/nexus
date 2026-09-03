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
