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

## Optional image generation edge (disabled by default)

A separate reviewed `POST /studio-api/generate-image` and
`GET /studio-api/image-generation-status` are available in source. These endpoints
require an operator-configured compatible image provider, explicit consent,
Studio authentication, a configuration fingerprint, and an attempt quota.
Only bounded PNG/JPEG base64 output is accepted; no generated image is retained
by NEXUS. The Studio chat source now contains an explicit review/consent panel for
this API. This **does not** provision a model or prove production availability. See [configuration, limitations and tests](../docs/STUDIO-IMAGE-GENERATION.md).

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

## Local model request attempt budget

The real-model gateway now has a **conservative per-process provider attempt
limit** to reduce accidental provider calls during early-stage use. With no
additional setting, each FastAPI worker admits up to **32** text-model requests
over its own process lifetime, counting buffered and streamed requests together.
The optional server-only setting is:

```sh
NEXUS_MODEL_MAX_REQUESTS_PER_PROCESS=8
```

Set any integer from `1` to `4096`; `0` intentionally disables model
provider calls. Missing means `32`. Malformed, negative or out-of-range values
fail closed (zero permitted calls). This setting is also forwarded by the
loopback-only `scripts/run-local-studio.py` launcher; it never goes to the
browser or third-party provider.

The worker checks the limit **only after** validating the separate Studio
authentication, explicit consent, input bounds, latest configuration review,
mode and payload. A denied or invalid request cannot drain the limit. A
permitted attempt is counted **before** its provider connection; failed,
timed-out, canceled, disconnected, or provider-rejected requests are never
refunded, because upstream cost may still have occurred. Exhaustion returns
HTTP `429` with a non-sensitive detail and no upstream provider call. For
the default **per-process** budget only, a restart resets the counter.

### Optional durable quota for one Linux host

A single-host installation with a persistent *local* filesystem can opt into
an owner-private, restart-persistent request count. Create the directory as
the **same operating-system account that runs FastAPI**:

```sh
install -d -m 0700 /var/lib/nexus/model-budget
```

Then supply this **server-only** environment variable:

```sh
NEXUS_MODEL_BUDGET_DIR=/var/lib/nexus/model-budget
```

The directory must already exist, be an absolute path, be owned by the
server's process user, have no group/other permissions, and not be a symlink.
NEXUS uses a Linux advisory lock on this directory for **all local worker
processes**, an owner-only counter file, atomic replacement and file/directory
`fsync`. Restarts or a second worker that uses **the same host directory**
will **not reset** its count. The existing `0`–`4096` attempt limit is
shared, and lowering it does not erase recorded attempts. If the directory is
missing, the counter is corrupt, permissions are unsafe, or storage I/O fails,
provider requests are **blocked** rather than silently falling back to a new
per-process allowance.

The private local launcher `scripts/run-local-studio.py` now enables this
feature automatically, using `provider-model-budget/` inside its existing
private `--state-dir`. It never inherits a custom budget directory from the
shell. The counter intentionally survives ordinary launcher restarts.

The authenticated operator-readiness diagnostic reports
`budget_scope: one_private_host_directory_until_explicit_reset` and a
shared `local_request_budget`. If storage is inaccessible it reports
`LOCAL_BUDGET_UNAVAILABLE`, `attempted: null`, and
`operator_next_step: repair_private_budget_storage` instead of pretending
the allowance has reset. The in-memory fallback remains available when
`NEXUS_MODEL_BUDGET_DIR` is **unset**, with scope
`one_process_until_restart`.

**Limits:** this is still a request-*attempt* count, **not a monetary cap**.
There is no cross-host, cross-container or cross-replica guarantee, nor
reliable persistence when the hosting filesystem itself is ephemeral.
The count may be lost with its volume, deleted by an operator, or bypassed by
using a provider credential outside NEXUS. File-locking semantics on network
filesystems are not supported. A container provider may require a separately
mounted persistent volume, which can cost money. NEXUS does not create one
or configure third-party billing. Independently enforce provider-side quotas,
spend caps and API-key controls before authorizing public use.

## Private, offline model-readiness diagnostics

Operators can inspect the actual running Studio gateway **without contacting
the model provider**:

```sh
curl --fail-with-body \\
  --header "Authorization: Bearer ${NEXUS_STUDIO_TOKEN}" \\
  "http://127.0.0.1:8000/studio-api/operator-readiness"
```

Use the gateway's real HTTPS address instead of loopback for a remotely hosted
instance. Never paste a real token into a browser URL, screenshot, repository
issue or shared command history.

The route requires the existing separate Studio operator bearer token (at
least 32 characters). An absent/short token disables diagnostics, even when
the model is unconfigured. Missing, wrong and duplicate authorization headers
are rejected. It returns `Cache-Control: no-store`, never includes model API
keys, Studio tokens, endpoint paths, user prompts, raw responses, billing data
or private files, and makes **zero provider requests**.

The response distinguishes:
- `NOT_CONFIGURED`: the model settings are missing or invalid
- `READY_TO_TEST`: the settings pass *local* validation and the per-process
  request guard has remaining attempts; this **does not prove a live model**
- `LOCAL_BUDGET_EXHAUSTED`: the worker has no remaining local attempts
- `LOCAL_BUDGET_UNAVAILABLE`: the explicitly configured private durable
  quota store is unsafe or unavailable, so all model calls are denied

It also shows the configured adapter/model/hostname (only to authenticated
operators), streaming setting and atomic in-process
`local_request_budget: {limit, attempted, remaining}`. The
`provider_live_verification: NOT_RECORDED` field is intentional:
NEXUS does not persist independent provider availability or trust evidence.
`operator_next_step` suggests server configuration, explicit one-question
smoke or reviewing the local cap; it never initiates these actions.

This endpoint is diagnostic, **not a user interface for API keys**, not a
cross-worker spending dashboard and not a remote-availability check. Counter
values change within one worker and reset on restart. Do not enable public
usage until provider account quotas, credentials, cost limits, stage deployment
and live-response validation have been independently verified.

## Optional Gemini model adapter (operator configured, text only)

NEXUS supports an explicitly selected `NEXUS_MODEL_ADAPTER=gemini` using
Google's [OpenAI-compatible Chat Completions API](https://ai.google.dev/gemini-api/docs/openai).
This is **not** automatic Gemini account integration, Google Search grounding,
Gemini tool calling, native multimodal file exchange, or evidence that any
particular model is available or produces high-quality answers.

Set the following in the **server's secret environment**, not in the website,
repository, issue, commit, or chat history:

```sh
NEXUS_MODEL_ADAPTER=gemini
NEXUS_MODEL_URL=https://generativelanguage.googleapis.com/v1beta/openai/chat/completions
NEXUS_MODEL_ID=<operator-selected-supported-gemini-model>
NEXUS_MODEL_API_KEY=<server-side-gemini-api-key>
NEXUS_STUDIO_TOKEN=<independent-random-secret-at-least-32-characters>
```

The Gemini adapter enforces this **exact HTTPS destination**, requires a
nonempty Gemini API key, does not forward Studio's access token, and does not
accept a custom host or alternate path while selected. Its requests use a
bounded `max_tokens` budget, the existing user-approved system policy and
text-only messages; it omits `store` rather than assuming the compatibility
API honors an OpenAI-specific retention control. Google's provider-specific
retention, billing, quotas and usage policies still apply. The separate
`generic` and `deepseek` adapters are unchanged.

The Studio UI exposes only `standard` mode for Gemini because reasoning
settings differ across Gemini model generations; `thinking` and
`non-thinking` requests are rejected rather than silently mapped to
unsupported controls. Optional streaming still requires
`NEXUS_MODEL_STREAMING=1` and is validated by the same bounded text-only
SSE parser. Tool calls, provider reasoning fields, and non-text results
are not executed or returned. A change of adapter or model invalidates
previously reviewed Studio model requests.

Check the operator-selected provider's current model support before configuring
it. For an explicitly consented **live** acceptance sample, use the fifteen
synthetic probes documented below; these do contact Google and may incur
charges. GitHub CI uses HTTPX mocks and does **not** access Google credentials
or perform a live Gemini model test.

## Immutable model-provider request snapshots

For every approved Studio model request, the gateway captures one validated
snapshot of the endpoint, model ID, provider adapter, streaming flag, Studio
access token, upstream API key and system policy **before reading the request
body**. A concurrent operator configuration rotation therefore cannot combine
the previously reviewed Gemini/DeepSeek/other provider URL with an unrelated
provider's fresh API key or payload semantics.

The configuration review ID additionally includes the **system policy digest**.
Changing model identity, adapter, streaming behavior or policy requires a
fresh browser review (HTTP 409 for the previous ID). Credentials are excluded
from the public fingerprint and status response; individual in-flight requests
use the captured secret, whereas new requests use newly configured credentials.
The immutable configuration object also hides credentials from its Python
representation. Status does not expose provider keys or the Studio token.

**Migration:** Existing reviewed Studio model requests from earlier gateway
versions need to refresh model status and be reviewed again after this release,
even when the operator leaves the provider unchanged. Do not bypass this
fail-closed migration.

Explicitly consented live quality evaluation similarly keeps one configuration
snapshot across its fifteen fictional prompts. This avoids mixed-provider
scores during a rotation. These tests do **not** establish a live hosted model,
privacy compliance, epistemic accuracy, or provider quality; the user still
must provide an authorized server-side credential and explicitly approve live
sampling. No extra model requests or provider credentials are created in CI.

## Run a real Gemini staging check from a phone (manual GitHub Actions)

The workflow `.github/workflows/manual-gemini-staging.yml` can run a
bounded, text-only staging check through GitHub Actions **without a computer**.
It is **manual-only** (no push, pull-request or scheduled trigger). It is
limited to the exact Gemini OpenAI-compatible endpoint, one operator-selected
model ID and fixed *fictional* source-controlled prompts. It cannot send
NEXUS conversations, files, voice recordings or personal information.

**One-time GitHub setup (in a browser):**
1. Open this repository → **Settings → Environments**. Create the
   `nexus-model-staging` environment. Limit deployment branches/tags to
   `main`; add required reviewers if your repository plan supports them.
   A workflow referencing an absent environment may create it automatically
   **without** protection, so configure it *before* entering a secret.
2. Under that environment's **Environment secrets**, add exactly
   `NEXUS_STAGE_GEMINI_API_KEY` with an API key obtained from your own
   authorized Gemini account. **Do not** put it in repository variables,
   workflow form inputs, chat messages, logs or commit history. A key is not
   supplied or generated by NEXUS. Confirm the provider's billing and quotas
   independently.
3. Open **Actions → NEXUS Manual Gemini Staging Check → Run workflow**;
   choose the `main` branch. GitHub may require the desktop browser layout
   on a mobile phone. Enter a currently supported Gemini `model_id` with
   letters, numbers, dots, underscores or hyphens (not a secret).

**Run modes:**
- `check_config` (default): **zero model-provider requests**, no billing
  acknowledgement. Checks only server credential/configuration shape. A pass
  means `READY_TO_TEST`, **not** that the remote model works.
- `single_smoke`: at most **one** external fictional prompt. In
  `billing_ack` type exactly `I_APPROVE_1_PROVIDER_REQUEST`.
- `full_quality`: at most **15** external fictional prompts. Type exactly
  `I_APPROVE_15_PROVIDER_REQUESTS` into `billing_ack`. This is a separate,
  stronger consent; a one-request acknowledgement cannot authorize fifteen.

The workflow rejects non-`main` dispatches and runs under
`nexus-model-staging`; the `GITHUB_TOKEN` has read-only contents permission,
the checkout does not persist credentials, setup actions are digest-pinned and
the provider secret is only delivered to the model job as an environment
secret. The Python entrypoint validates mode, exact acknowledgement, model ID
and secret formatting **before** creating any model network client. No
automatic retries, fallback providers, arbitrary endpoint override, uploads,
or user data are involved. The worker uses an ephemeral private Studio token
rather than asking you to save one as a second GitHub secret.

The Actions log shows only sanitized JSON: success/failure/error category and
synthetic probe IDs/scores, **not** prompts, model responses, provider keys or
model request URLs. The 15-question evaluator stops on upstream errors rather
than making all remaining calls. A run can still incur GitHub Actions minutes
or provider charges, even when the response fails. Running the workflow again
may incur additional charges. No action in this workflow deploys NEXUS or
proves it suitable for public use.

If you cannot create the environment or obtain an authorized API key, leave
the secret unset; GitHub will show `provider_secret_missing` and the workflow
will not contact Gemini. The local and CI synthetic tests remain available
without external provider access. Never copy actual provider credentials into
a public issue or ask another person to send them in chat.

## Optional synthetic model-answer quality evaluation

The operator can test a real configured provider against fifteen short **fictional** prompts spanning source grounding,
missing evidence, provenance, Persian, conflicting sources, untrusted instructions,
honest action claims, arithmetic, strict JSON, rewriting, code structure, constrained
choices, absent-file honesty, emergency triage, and irreversible actions. The probes use the same system policy and buffered
response-validation contract as the production Studio model bridge.

The default offline check **does not contact a model** and scores canned correct
responses. It verifies only the evaluator's mechanics:

```sh
cd nexus-cloud
uv run --frozen python -m model_quality_eval --self-test
```

### Three-step model readiness ladder

Before spending provider credits or routing any real user prompt, an operator
can perform progressively stronger checks. No ChatGPT account, Gemini login,
free quota or cloud model is automatically provisioned by these commands.

**1. Configuration check — zero network requests and no provider charges**

```sh
cd nexus-cloud
uv run --frozen python -m model_quality_eval --check-config
```

This verifies that the selected provider URL, adapter, model ID, separate
Studio token and any required server-side provider key meet the local
configuration contract. Output is deliberately redacted: it prints
`READY_TO_TEST` or `NOT_READY`, never the API key, endpoint, model name
or Studio token. **READY_TO_TEST does not establish live model availability.**

**2. Single fictional-question smoke — exactly one attempted provider request**

```sh
NEXUS_QUALITY_EVAL_CONSENT=YES uv run --frozen python -m model_quality_eval --smoke-live
```

This opt-in check sends only the fixed fictional `supplied_fact` probe through
the exact production text-only payload/acceptance contract, using the pinned
model/secret/policy snapshot. It does not send existing conversations, project
files or personal information, follow redirects or retry. It prints
`PASS`, `FAIL` or `ERROR` and the probe ID but never the answer or
credentials. Upstream provider policy, quotas, billing and latency still apply.
`PASS` means one basic reply met one heuristic criterion; the report
explicitly states `quality_gate: NOT_RUN` and
`live_model_evaluated: false` to prevent a smoke test from being mistaken
for the full acceptance suite.

**3. Full optional quality sample — fifteen provider requests**

After independently verifying permission, cost/quota and model identity,
use the `--live` command below. That is the larger heuristic quality gate.
Neither step is production acceptance by itself; human review and staging
evidence remain necessary.

For an **explicitly approved, live** quality sample, configure
`NEXUS_MODEL_URL`, `NEXUS_MODEL_ID`, `NEXUS_STUDIO_TOKEN` (minimum 32
characters), and, when required, `NEXUS_MODEL_API_KEY` securely in the
operator's environment. The live test makes fifteen external model requests
and may incur provider charges. It sends **only the fixed fictional prompts**,
not stored user conversations, project files, or private data:

```sh
NEXUS_QUALITY_EVAL_CONSENT=YES uv run --frozen python -m model_quality_eval --live
```

The command refuses a live run without explicit consent or a valid configured
provider. It exits nonzero if a probe encounters a provider/transport error or
if the selected pass-rate threshold is not reached (default 0.85; override
with `--minimum-pass-rate`), **or if any critical trust/safety probe fails**
(even when the average exceeds the threshold).

**Fail-fast on provider failure:** if the first attempted probe encounters a
401/403 authentication failure, 402 billing failure, 429 rate limit, upstream
5xx rejection, malformed response, timeout or connection error, the evaluator
stops rather than sending the remaining 14 requests. A later failure likewise
stops the rest. There are **no retries, credential refresh attempts, or automatic
fallback providers**. A well-formed answer that is simply wrong does **not**
stop the evaluation: all remaining probes still run.

Results distinguish `PASS`, `FAIL`, `ERROR` and **`SKIPPED`** (unattempted),
with `provider_requests_attempted`, `provider_requests_skipped`,
`aborted_early`, and `abort_reason`. Partial evaluations **cannot pass**,
even at a zero pass-rate threshold. Provider errors use fixed public classes
(`authentication`, `billing`, `rate_limited`, `request_rejected`,
`upstream_unavailable`, `invalid_response`, `transport_or_validation`).
HTTP error response bodies, URL, tokens, raw answers, and exception text are
never copied into the JSON report.

The single-question `--smoke-live` check now also includes a sanitized
`error_reason` on failure. The JSON quality report contains only probe IDs,
dimensions, critical flags, outcome categories, failure IDs and aggregate
counts; it never prints raw answers or provider credentials. `trust_env=False`
avoids unintended ambient HTTP proxy configuration.

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
