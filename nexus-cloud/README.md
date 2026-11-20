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
- `studio_model.py` - optional consent-gated model bridge
- `transport_bounds.py` - shared strict Content-Length, body-size and deadline admission
- `tests/test_admission_shared.py` - cross-edge authorization/framing regressions
- `tests/test_contract.py` - transport-boundary contract tests
- `pyproject.toml` / `uv.lock` - locked Python environment

## Optional Studio model bridge

This adapter also exposes `/studio-api/status` and `/studio-api/respond`. Model
use is disabled unless `NEXUS_MODEL_URL`, `NEXUS_MODEL_ID` and the separate
`NEXUS_STUDIO_TOKEN` are configured by the operator. The optional provider key
`NEXUS_MODEL_API_KEY` remains on the server. The endpoint accepts only reviewed
text messages and has no tools. See [Studio setup and limits](../docs/STUDIO-CAPABILITIES.md).

Set `NEXUS_MODEL_STREAMING=1` only on a gateway whose configured Chat
Completions provider supports SSE. Studio lists streaming delivery in the
request review and sends approved requests to `/studio-api/respond-stream`.
The endpoint returns UTF-8 newline-delimited JSON. `delta` frames carry visible
answer text, `done` confirms an accepted provider finish, and `error` means no
answer was completed. Provider reasoning fields stay on the gateway. Older
clients and gateways can continue using the buffered `/studio-api/respond`.

Streaming uses the existing four-request model capacity, a 45-second total
provider deadline and a 128,000-byte upstream limit. The browser keeps the
original draft if the user stops the stream or if it fails. It adds an answer
to the conversation only when a valid stream completes. A stopped or failed
request can still count against the provider's usage.

Deploy from the repository root to include the optional `/studio` HTML page.
A gateway-only deployment may use an explicitly configured `NEXUS_STUDIO_ORIGIN`
with Studio hosted separately. There is no provisioned model or live provider
quality test in this repository's synthetic acceptance suite.

## Optional synthetic model-answer quality evaluation

The operator can test a real configured provider against seven short **fictional**
prompts covering supplied facts, missing evidence, named source/line attribution,
Persian answers, conflicting sources, untrusted text instructions, and honest
claims about actions. The probes use the same system policy and buffered
response-validation contract as the production Studio model bridge.

The default offline check **does not contact a model** and scores canned correct
responses. It verifies only the evaluator's mechanics:

```sh
cd nexus-cloud
uv run --frozen python -m model_quality_eval --self-test
```

For an **explicitly approved, live** quality sample, configure
`NEXUS_MODEL_URL`, `NEXUS_MODEL_ID`, `NEXUS_STUDIO_TOKEN` (minimum 32
characters), and, when required, `NEXUS_MODEL_API_KEY` securely in the
operator's environment. The live test makes seven external model requests
and may incur provider charges. It sends **only the fixed fictional prompts**,
not stored user conversations, project files, or private data:

```sh
NEXUS_QUALITY_EVAL_CONSENT=YES uv run --frozen python -m model_quality_eval --live
```

The command refuses a live run without explicit consent or a valid configured
provider. It exits nonzero if a probe encounters a provider/transport error or
if the selected pass-rate threshold is not reached (default 0.85; override
with `--minimum-pass-rate`). The JSON output contains only probe IDs,
dimensions, pass/fail/error verdicts, and aggregate scores; it never prints raw
answers or provider credentials. `trust_env=False` avoids unintended ambient
HTTP proxy configuration.

**Interpretation:** These are simple deterministic checks on artificial
examples, not independent fact verification, a safety certification, a
real-world accuracy score, or proof that the model can cite arbitrary sources
correctly. The offline CI result explicitly says
`live_model_evaluated: false`; no funded or deployed provider is implied.
Do not use this score alone to authorize public deployment or professional
decisions. Human review, broader adversarial tests, real-provider acceptance,
and independent operational evidence remain separate requirements.

## Gateway capacity and deadlines

Each worker admits at most 16 concurrent `/v1/*` requests, including callers
still uploading bodies. Excess callers receive `503`, `Retry-After: 1` and
`Cache-Control: no-store` before the adapter reads their bodies. Capacity is
released on completion, validation errors, disconnection and cancellation.
This is a per-worker resource bound, not a per-user rate limit.

Body ingestion has a 30-second deadline. A separate 30-second total upstream
deadline covers connection-pool wait, connection, response headers and the
complete response body; progress cannot extend it indefinitely. Existing
1 MiB request and 4 MiB response limits still apply. An upstream timeout returns
a generic `503`; the adapter never automatically retries an opaque operation.
A timeout does not prove that the core did not accept a mutation; callers must
reconcile request state before deciding to resubmit.

## Shared cloud admission boundary

The delegated core API and Studio model API use the same bounded streaming reader.
Both reject duplicated or contradictory HTTP request framing, including a
Content-Length/Transfer-Encoding combination and declared/received length
mismatch. Both reject duplicate Authorization headers. The Studio model edge
additionally requires an exact JSON media type, not a string prefix. The core
limit remains 1 MiB / 30 seconds; the Studio input limit remains 96,000 bytes /
45 seconds. The client-side model toggle does not bypass either server policy
or consent review. See
[`docs/CLOUD-TRANSPORT-ADMISSION-BOUNDARY-2026-11-17.md`](../docs/CLOUD-TRANSPORT-ADMISSION-BOUNDARY-2026-11-17.md)
for invariants, tests, and the evidence boundary.


## Studio connections

Open **Connections** beside the chat tools. Set the Studio gateway URL and its
operator access token, then load the configured connections. Pick a read action,
review the displayed target, and approve the read. **Attach to next message**
makes a separate temporary attachment. Sending the text to a configured model
uses the normal Studio review and consent flow.

Configure connections on an owner-only adapter. All settings below are optional
except the Studio operator token when the API is used.

| Setting | Purpose |
| --- | --- |
| `NEXUS_STUDIO_TOKEN` | Operator authentication (at least 32 characters). The local launcher creates its own token file. |
| `NEXUS_CONNECTOR_GITHUB_REPO` | One repository, in `owner/repository` form. |
| `NEXUS_CONNECTOR_GITHUB_TOKEN` | Optional fine-grained token for the selected repo. Use Contents read and Pull requests read permissions. Public repositories can be read without a provider token. |
| `NEXUS_CONNECTOR_GITHUB_BRANCH_TOKEN` | Optional separate token for the selected repository, with Contents write permission. Enables reviewed branch creation. |
| `NEXUS_CONNECTOR_GITHUB_FILE_TOKEN` | Optional separate token for the selected repository, with Contents write permission. Enables reviewed edits to existing files on Studio work branches. |
| `NEXUS_CONNECTOR_RENDER_SERVICE` | One Render service ID. |
| `NEXUS_CONNECTOR_RENDER_TOKEN` | Server-side token with the narrowest available deployments read scope. |
| `NEXUS_STUDIO_ORIGIN` | Exact public Studio origin when the UI and adapter run on different origins. |

For local use, set the applicable connector environment variables before starting
`uv run --project nexus-cloud --frozen python scripts/run-local-studio.py`.
For remote use, put provider credentials in the owner's gateway secret settings.
Only the Studio operator token goes into the Studio gateway field. Choose a
gateway you control. Clear the provider token or target and restart the gateway
to disable the private provider connection.

The GitHub actions read open pull requests and UTF-8 files up to 24 KiB. The API
also accepts an optional full Git commit SHA when reading a file. Render reads
the latest eight deployments and returns only their identifiers, states, commit
SHAs and creation times. Provider output is external context for review. This
registry uses server-side credentials. With the separate branch token, Studio
can review the current `main` commit and create `nexus/studio-<name>` at that
exact commit after a second confirmation. Reviews expire after five minutes.
Changing the base or branch name requires a fresh review. Existing branches are
never moved. A retry can recognize the same branch and commit. Branch creation
can trigger GitHub workflows configured to run on branch pushes. With the separate file token, **Edit a file** loads one regular, non-executable
UTF-8 file on a `nexus/studio-*` branch. Change the text, review the line diff,
then confirm a single-file commit. GitHub compares the exact expected branch
head atomically when committing. Reviews expire in five minutes, and changing
the text or target invalidates the approval. File edits are bounded to 24 KiB
and 1,800 LF lines. Hidden directories, binary files, symlinks and executable
modes are excluded. Pull-request creation, OAuth and deployment triggers remain
outside these endpoints.
