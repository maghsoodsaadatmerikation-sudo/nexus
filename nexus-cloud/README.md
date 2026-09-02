# NEXUS Cloud Adapter

This FastAPI service is a deliberately non-authoritative transport adapter in
front of the NEXUS Rust gateway. It authenticates the presence of a bearer
credential, forwards opaque `/v1/*` requests, and preserves upstream HTTP
status codes—including the `202 Accepted` / `pending` request contract.

It does **not** authorize actions, interpret evidence, create human judgments,
execute constitutional actions, mutate policy, or persist NEXUS workspace
state. Those responsibilities remain in the Rust constitutional core.

## Configuration

- `NEXUS_CORE_URL` (required for `/v1/*`): HTTPS base URL of the deployed Rust
  gateway. Do not include a trailing slash.

The caller's `Authorization: Bearer ...` header is passed to the Rust gateway;
tokens are not stored by this adapter.

## Local development

```sh
uv sync --locked
uv run pytest
uv run fastapi dev
```

Operational liveness is available at `/healthz`. A successful health response
is not evidence of epistemic correctness or constitutional authorization.

A project created with FastAPI CLI.

## Quick Start

### Start the development server

```bash
uv run fastapi dev
```

Visit http://localhost:8000

### Deploy to FastAPI Cloud

Sign up and log in at https://fastapicloud.com, then deploy with:

```bash
uv run fastapi deploy
```

## Project Structure

- `main.py` - Your FastAPI application
- `pyproject.toml` - Project dependencies

## Learn More

- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [FastAPI Cloud](https://fastapicloud.com)
