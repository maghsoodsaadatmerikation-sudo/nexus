# Stage D — explicit Railway credential scope for private Volume capture

**Status: scoped manual workflow implemented; original production Volume has NOT been downloaded or independently restored.** This page explains the credentials accepted by [the manual encrypted capture workflow](../.github/workflows/stage-d-encrypted-volume-capture.yml). Do not post secrets in GitHub Issues, workflow inputs, this conversation, files or logs.

## The issue addressed

The Railway CLI accepts different token classes: a project-scoped token is conventionally read from `RAILWAY_TOKEN`, and an account/workspace API token from `RAILWAY_API_TOKEN`. The existing workflow supported the project token only, without an explicit way to select the other scope if the Railway Volume file API rejected it. Silently switching to a more powerful token would be unsafe. **The exact authorization needed for real `volume files download` has not been tested with a real credential.**

## Manual operator-controlled decision

The default selection is **`project`**, intended to be the narrower credential. Supply the project's production environment token in the private repository Actions secret named `NEXUS_STAGE_D_RAILWAY_TOKEN`. Select `project` in the manually dispatched workflow. Leave the workspace acknowledgement empty. If the account/plan does not grant project tokens access to volume file downloads, the workflow must fail, not silently fall back.

If, **only after** verifying the real API limitation and consciously accepting the broader credential exposure, the authorized owner chooses **`workspace`**, create a separate trusted workspace API token via Railway's official private settings, store it exclusively in the repository Actions secret named `NEXUS_STAGE_D_RAILWAY_WORKSPACE_API_TOKEN`, select `workspace`, and enter this exact workflow input:

```text
I ACCEPT WORKSPACE TOKEN SCOPE
```

No value should ever be pasted into the confirmation input. The chosen credential is available **only in the read-only download step**; the other credential is not selected. Two simultaneous nonempty auth variables within the Python capture process are rejected before a CLI invocation or private download directory creation. No permissions are automatically escalated.

Both methods still require a separate manual `confirm_volume` input with the exact original Volume ID `cc47a350-6c7e-4487-89d9-c4b390f94884`, and the workflow is only dispatchable on `main`. An unsupported/unknown scope, missing selected secret or incorrect acknowledgement is a BLOCK, without a volume operation. There is no secret registration or workflow dispatch connector action in this chat; the currently connected Railway integration does **not** expose secret values or Volume content. These are prerequisites to the real capture, not tasks already completed.

## What happens after a successful selected-scope download

The existing pinned CLI only attempts an exact-target `volume files download /` with concurrency one. The private copied data is structurally scanned and restored into an isolated quarantine rehearsal. Only the three validated private evidence records are encrypted with the pinned **public** recovery certificate, and only ciphertext + sanitized JSON are placed in a 7-day private GitHub Actions artifact. A non-secret SHA-256 log anchor can later help detect post-run file substitution. The owner-held private RSA key **must not be added to GitHub or Railway**.

Even successful encrypted capture and local rehearsal would not independently prove Railway origin, complete/atomic point-in-time data consistency or real independent host recovery. The operator must preserve encrypted bytes outside the temporary artifact retention and independently verify a genuine restore before acceptance.

## Tested negative cases and self-critique

- The Python downloader refuses both `RAILWAY_TOKEN` and `RAILWAY_API_TOKEN` simultaneously, or neither, before touching the provider or creating destination data.
- Unit tests run the **actual Bash preflight extracted from the workflow** using synthetic credentials: missing tokens, invalid scope, wrong or missing workspace acknowledgement, attempted fallback and no token exposure in logs. They verify that download, encryption, log hashing and artifact upload steps remain separately scoped.
- The fake Railway CLI verifies project-token-only and workspace-token-only download modes with no real network calls.
- **No automatic token class detection exists.** API grant scope, Railway billing and download support remain to be checked in the first real, explicitly authorized manual run. A broader workspace token has greater blast radius if the runner or its dependencies are compromised. A CI runner is **not** a hardware-secure enclave; removing plaintext afterward is best-effort.
- Credentials cannot be read, created or dispatched by this connected GitHub/Railway toolset. Never simulate a live download merely to report progress.

These tests protect selection and prevent implicit credential escalation. They **do not** grant a backup, release Seal or first-user authorization. [Issue #70](https://github.com/maghsoodsaadatmerikation-sudo/nexus/issues/70) stays OPEN. `A_out <= A_in`.
