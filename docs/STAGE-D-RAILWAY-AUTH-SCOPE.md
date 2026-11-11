# Stage D — Explicit Railway credential scope for private encrypted capture

**Status (2026-11-11): implemented and synthetically tested; no production
Volume files downloaded, no GitHub Actions secret created, and no manual
capture workflow dispatched.** This is a safer operator-controlled **choice
of authentication scope**, not an authorization grant or a backup.

## Why this is necessary

Railway's [CLI login documentation](https://docs.railway.com/cli/login)
documents two different noninteractive credentials and explicitly says they
**must not be set simultaneously**:

- **Project token:** `RAILWAY_TOKEN`; scoped to a project/environment.
- **Account/workspace token:** `RAILWAY_API_TOKEN`; broader authorization.

Railway's [deployment documentation](https://docs.railway.com/cli/deploying)
primarily demonstrates Project Token for deployment-related operations.
Therefore **project-token permission for** `railway volume files download`
**is unproven**. Do not label a synthetic CLI parser test as evidence of
authorized real file access, and do not automatically upgrade authorization
to a workspace token in response to a denied project token.

## Operator action (private GitHub/Railway web UIs)

The manual-only [capture workflow](../.github/workflows/stage-d-encrypted-volume-capture.yml)
now has an explicit `credential_scope` selector, default `project`.

**Default: project**

1. In Railway's authenticated Project Settings > Tokens UI, create a
   dedicated **environment-appropriate Project Token** (subject to the
   account's own access/billing constraints).
2. Add the value **privately in GitHub Settings > Secrets and variables >
   Actions** as repository secret `NEXUS_STAGE_D_RAILWAY_TOKEN`. Never send
   or paste token values in a chat, issue, PR or workflow input.
3. In the manual workflow UI, choose `project`, keep
   `confirm_workspace_scope` **empty**, and enter the exact original
   Volume UUID into the existing confirmation field:
   `cc47a350-6c7e-4487-89d9-c4b390f94884`.
4. If the actual authenticated read-only download refuses access, record
   only the sanitized failure status (not CLI stdout/stderr or filenames).
   **Do not infer** that any file was captured; no fallback occurs.

**Exceptional: workspace (explicit broader privilege)**

Only if the project-scoped method cannot authorize Volume file reads and
the account owner **independently authorizes** the increased exposure:

1. Review the broader account/workspace permissions and consequences before
   creating a token. The workspace token may access unrelated resources;
   it must not be obtained, copied, or stored automatically. Prefer a
   narrowly scoped option wherever the provider permits it.
2. Create a dedicated account/workspace API token privately in Railway.
   Set it in GitHub Actions under the **different** secret name
   `NEXUS_STAGE_D_RAILWAY_WORKSPACE_API_TOKEN`. Never overwrite the project
   token with it.
3. In the **manual** capture workflow, select `workspace` and enter the
   exact acknowledgment `I ACCEPT WORKSPACE TOKEN SCOPE` in
   `confirm_workspace_scope`. Reconfirm the exact original Volume ID.
4. Only the **selected** secret is injected into the one provider-download
   process. The default Project Token is not passed at the same time;
   unselected credentials are not a fallback. Treat temporary Actions
   runner custody as a real risk when deciding whether to use this scope.
5. Once the encrypted artifact and separately verified real recovery have
   been preserved in owner-controlled storage, revoke unnecessary tokens
   using the provider's dashboard. Revoking is an owner-controlled security
   action; this repo does not do it automatically.

## Implemented fail-closed boundaries

- **Before downloading even the public CLI binary**, the workflow validates
  the selected scope, exact manual acknowledgment for workspace, and
  presence of **only its selected secret**. Unknown mode, missing secret,
  both-scopes-at-once, project mode with a workspace acknowledgment, or
  workspace mode without explicit consent each halt the job.
- The actual download step's `RAILWAY_TOKEN` and `RAILWAY_API_TOKEN`
  environment variables use **mutually exclusive conditions** on the
  selector, and only its exact CLI process can inherit the selected
  credential. Help/version probes, private intake, encryption, receipt,
  log-anchor, and artifact upload receive no Railway credential.
- The Python driver independently enforces exactly **one** nonempty Railway
  credential before any provider CLI invocation or private output creation.
  No secret values appear in success, refusal or test output.
- No manual workflow input contains a credential value. The explicit volume
  UUID acknowledgment remains mandatory, and the job runs on `main` only.
- CI invokes the workflow's **real inline Bash preflight** with synthetic
  token presence under 13 tests, including unauthorized combinations.
  Separate fake-provider integration checks exercise both project-only and
  workspace-only download and simultaneous-token rejection.
- Authentication *synthetic correctness* is not provider authorization.
  Neither mode is guaranteed to work until a legitimate user executes it
  against the actual Railway account. The workflow remains **manual-only**.

## Unchanged recovery and authority boundary

This stage does **not** obtain the secret, trigger a job, read original
Railway `/data`, modify/detach/redeploy a Volume, activate any paid service,
or assert a backup. An encrypted GitHub artifact and receipt (7-day
retention) also cannot alone establish point-in-time consistency or
independent live restore.

A successful future run must still pass the
[encrypted log anchor](STAGE-D-RUN-LOG-ANCHOR.md), the
[owner-held independent offline restore](STAGE-D-ENCRYPTED-OFFLINE-RECOVERY.md)
and actual operator-witnessed evidence. No Seal or release is granted.

[Issue #70](https://github.com/maghsoodsaadatmerikation-sudo/nexus/issues/70)
stays OPEN, and `A_out <= A_in`.
