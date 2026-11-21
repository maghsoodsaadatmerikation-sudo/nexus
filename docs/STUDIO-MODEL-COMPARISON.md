# NEXUS — comparison of configured model routes (opt-in)

NEXUS supports comparing the *configured* primary, secondary and tertiary routes on the **same fixed, fictional text-only probes**. This workflow cannot determine which model is universally best, and it must not be confused with a production trial, a safety certification, or a billing cap in dollars.

## Preconditions

- Configure two or three valid model routes on a private Studio gateway using the operator-only variables documented in [the cloud adapter](../nexus-cloud/README.md).
- Keep each upstream API key in the server environment. Do **not** put provider keys in the browser, chat, GitHub pull request, logs or CLI flags.
- Use a private environment where you control provider credentials and spend limits. The runner never loads real conversation histories.
- Set **provider-side hard budget/quota ceilings independently** before a paid run. NEXUS can count requests, but cannot know a provider's current prices, cached-token policies, future pricing changes, or final invoice.

From the repository's \`nexus-cloud\` directory, with the frozen Python dependencies installed:

**Preflight — guaranteed zero model calls:**

\`\`\`bash
python model_quality_compare.py --check-config --slots primary,secondary
\`\`\`

The report contains only selected slot names and boolean configuration statuses. It does not expose URLs, model IDs, credentials or request text.

**Two-model smoke — at most 2 model requests:**

\`\`\`bash
export NEXUS_MODEL_COMPARE_CONSENT=YES
export NEXUS_MODEL_COMPARE_ACK=I_APPROVE_2_PROVIDER_REQUESTS
python model_quality_compare.py --smoke --slots primary,secondary --max-requests 2
\`\`\`

The smoke checks one fictional prompt per selected model. Its success confirms only that one reply passed a narrow format/content check. It is **not** a quality comparison: \`comparable=false\`, \`quality_gate=NOT_RUN\`.

**Full comparison — at most 30 provider requests for two models:**

\`\`\`bash
export NEXUS_MODEL_COMPARE_CONSENT=YES
export NEXUS_MODEL_COMPARE_ACK=I_APPROVE_30_PROVIDER_REQUESTS
python model_quality_compare.py --full --slots primary,secondary --max-requests 30
\`\`\`

For three selected models, the full run uses exactly **45** as the request ceiling and \`I_APPROVE_45_PROVIDER_REQUESTS\`. Three-model smoke uses **3** and \`I_APPROVE_3_PROVIDER_REQUESTS\`. You may compare any two of \`primary\`, \`secondary\`, \`tertiary\`, provided both are currently configured. Duplicates, unknown names, malformed counts, fuzzy consent, a missing slot and extra CLI endpoints are rejected.

## Safety and interpretation

The command validates **all slots and both explicit approvals before creating a network client**. Its \`AttemptCap\` counts an attempt *before* handing it to HTTPX; cancelled, failed or redirected requests are not refunded. It sets \`trust_env=False\`, disables redirects, uses existing provider-specific text-only envelopes and 45-second request timeouts, and has no retry logic. A provider rejection or invalid response aborts the rest of the comparison instead of contacting other routes automatically. It does not execute tools or let an answer choose another endpoint.

The fixed full suite has 15 synthetic, nonpersonal cases covering grounding, provenance, uncertainty, multilingual output, instruction-boundaries, basic coding and arithmetic, decision support, and safety/ability honesty. The results contain aggregate counts, fixed case identifiers and a **heuristic order** only when every selected model completes the full suite; no raw model answers, prompts, credentials, private URLs or user files are reported. A full suite may be \`comparable=true\` yet have \`status=FAIL\` when a model fails a heuristic threshold or a critical case. \`truth_claim\` remains \`NOT_PROVEN\`.

This workflow's maximum provider attempts is **not** a financial expenditure limit. The fixed 256-token response allowance does not bound all prompt token charges or provider-specific pricing. Provider-side spend and account-level quota controls are mandatory for predictable monetary risk. A comparison cannot demonstrate production readiness, medical reliability or parity with commercial assistants.

The existing user-facing Studio request-attempt guard and browser one-shot consent still apply independently; this CLI is an **operator-only**, separately approved benchmark.

## Run from a phone with GitHub Actions

After this change is merged into the default `main` branch, open the repository's
**Actions → NEXUS Manual Model Comparison — Capped and Consent-Bound → Run workflow**.
The workflow has **no push, pull request, schedule, or automatic trigger**.

Before the first run, the repository owner must configure and protect the GitHub
Actions environment named **`nexus-model-comparison`** with required reviewer
approval if supported by their repository plan. Set a strong random
`NEXUS_COMPARE_STUDIO_TOKEN` (at least 32 characters) and the separate
`NEXUS_COMPARE_PRIMARY_API_KEY`, `NEXUS_COMPARE_SECONDARY_API_KEY` and optional
`NEXUS_COMPARE_TERTIARY_API_KEY` as **environment secrets**. Put the associated
`NEXUS_COMPARE_PRIMARY_URL`, `_ID`, `_ADAPTER` and similarly prefixed
secondary/tertiary values into environment **variables**, alongside optional
`_STREAMING`. Put each optional `NEXUS_COMPARE_<SLOT>_WORKSPACE_ID` into
**environment secrets**, not visible configuration variables. These configuration values are mapped to
the corresponding server-side `NEXUS_MODEL_*` fields by the workflow; the
provider keys are never accepted as run inputs.

Start with **`check_config`**, without billing consent, to confirm valid
private route configuration without provider calls. Only then select
`single_smoke` or `full_quality`, choose the slots and specify `YES`, the
exact `max_requests` and matching `billing_ack`. An independent source-guard
job checks main branch and exact approval **before** the secret-enabled job
can run; the Python runner enforces the same contract again.

If the environment, secrets, supported model IDs, subscription quotas or
hosting permissions have not been configured, the action is **not ready for a
real paid test**. Its existence does not mean providers are connected.
The workflow emits only redacted JSON; no raw-provider answers are uploaded.

## Auditable result receipt — review only, never deployment authority

Every approved GitHub Actions comparison stores a bounded **allowlisted JSON
receipt** as the `nexus-model-comparison-evidence` artifact for **14 days**,
including when the synthetic benchmark fails. The raw in-memory model answers
never enter either artifact or workflow logs. The private intermediate JSON
is kept only in the ephemeral GitHub Actions runner and not uploaded.

The receipt records the exact 40-character checkout commit, GitHub run ID
and run attempt, selected fixed model slots, the aggregate outcome and
total attempted provider requests. The original comparison JSON is parsed
with duplicate-field rejection and a 32 KiB size limit. Unknown fields,
a provider credential, full endpoint, raw answer, an inflated score,
a forged release approval or inconsistent attempt counts cause the receipt
builder to fail **closed**. There is no automatic retry or fallback to
another provider when the upstream comparison errors.

The artifact contains `receipt_sha256`: an unkeyed SHA-256 digest of the
canonical redacted receipt. This detects accidental tampering **when a trusted
artifact copy/digest is retained** but is **not an independent signature**,
remote-provider attestation, invoice validation or proof of the actual service
deployment. The reported GitHub run identity is runtime-supplied context;
users must corroborate it against the corresponding real Actions run and commit.

To validate a downloaded artifact locally:

```sh
cd nexus-cloud
python -m model_compare_evidence --verify --artifact /path/to/nexus-model-comparison-evidence.json
```

A successful verification can only report
`RECEIPT_DIGEST_AND_SCHEMA_PASS`. It **cannot** authorize release; every
receipt contains `release_state:
HOLD_INDEPENDENT_PROVIDER_COST_DEPLOY_AND_ROLLBACK_EVIDENCE`, plus explicit
false values for deployment permission, public origin verification, real
provider billing verification, independent provider-response attestation
and Render rollback verification.

Before any public production claim, obtain a separate currently verified
service/workspace identity, provider access and account quota evidence,
independent public HTTPS/Chromium acceptance, owner-device/archive testing,
an **actually restorable** prior deployment and explicit service-specific
owner authorization. The public static Studio release candidate and
existing independent read-only Render witness workflows remain separate.
No comparator artifact initiates an Actions deployment, Render build,
Railway change, expense or model call by itself.

## Release gate

- CI runs exclusively with HTTPX mocks: no operator secrets and no paid provider connections.
- Validate deterministic Studio assets and browser consent tests before merging.
- A real provider smoke must be an explicit operator action from a controlled environment.
- A real full comparison must be separately approved for its exact number of requests.
- Do not claim that a model is online, accurate, safe or generally superior from simulated CI results.
- Deploy only after reviewing the target host environment, secret permissions, data policy and rollback path. CI success alone does not constitute public deployment.
