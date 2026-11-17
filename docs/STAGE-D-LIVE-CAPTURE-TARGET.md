# Phase 38 — Reconcile the active Railway deployment before attempting private Stage D capture

**Checked against the connected Railway account on 2026-11-17.** This work is code/configuration correction and **synthetic tests only**. Neither provider Volume files nor any private credentials have been read. No backup workflow was dispatched, volume detached/moved, service awakened/redeployed or paid plan selected.

## Concrete defect found

The previous read-only Stage D capture helper `scripts/capture-railway-volume-readonly.py` had a **historical removed** deployment/commit hardcoded into its final local offhost intake report:

- Historical deployment `db2fd959-918e-49d5-b077-1ac74fac9a82` — provider list now reports `REMOVED`.
- Historical source commit `3c0977f4c7fc9fb5e9a78bdb1eeb581cb3cb4959`.

Connected provider read-only inventory instead reports:

- Project `2ac7887b-d67a-48be-8a7b-bd54092893ae`; production environment `56c4bc45-0e62-4aa9-832f-884bb1aa620c`.
- Original service `0032fc74-2c52-475d-b9df-9dca59237d93`; original attached volume `cc47a350-6c7e-4487-89d9-c4b390f94884` at `/data`, region `sfo`.
- **Latest deployment `32cdcb2b-c03c-4a6f-b028-27a9977717ce`**, created 2026-11-13, observed as `SLEEPING` on 2026-11-17.
- **Deployed source commit `9abbc067aad3ebbb0956432cf6682d2ea70e2824`**, different from GitHub's newer `main`.
- One **unapplied staged environment patch** remains: `healthcheckPath` `/` → `/readyz`, plus a no-op sleep setting; it was **NOT applied**.

The prior copy/restore tooling would have associated any later downloaded data with the **wrong removed deployment and source commit**, even though its provider-origin fields correctly said unverified. The Stage D archival integrity contract must not publish a false current revision label.

## Correction in this phase

1. The capture's static **expected** deployment and source constants now match the latest read-only provider inventory; the original Volume/project/environment/service IDs remain unchanged.
2. **Before any execution-side CLI parser check, volume transfer, or private output creation**, `--execute` now requires both `--confirm-deployment` and `--confirm-runtime` to equal those exact expected values. Missing, historical, drifted, uppercase or malformed values block without a copy. The default mode remains plan-only.
3. The manual-only GitHub workflow now requires the exact two new string inputs `confirm_deployment` and `confirm_runtime`, verifies both in its first no-secret Bash preflight, and passes them to the actual capture code. All previously existing original-volume, recovery-key and least-privilege token guards remain.
4. The immutable, historical v1.7 source fixture `3c0977f4...` and its legacy parity audit intentionally remain historical. Only **current-target** receipt metadata and synthetic test fixtures are reconciled; historical release evidence must not be rewritten.
5. New tests execute the **actual first Bash preflight** with synthetic environment and no cloud secrets, and try historical/missing/wrong source identities. Fake-provider download tests also prove these conditions block before creating the private capture directory. The dedicated Stage D CI now executes them.

## Phone-only owner checklist for a future *manual* backup attempt

**Do not run the capture if you cannot prove the owner-held matching recovery private key can actually decrypt a challenge locally.** The current workflow has never established key custody. Do not put the key, a token, any personal data or a key passphrase in ChatGPT, the repository, or an Action input.

After local recovery-key proof, open the authenticated Railway Project → production → `nexus-stage-d` → Deployments and **independently recheck** the currently selected deployment ID, deployed Git source SHA, original attached Volume ID and operational access. These observed IDs can change at any time. If either differs from this phase's pinned values, **stop** and revise/review the repository contract; do not enter historical values just to satisfy the form.

Then, subject to account access, potential charges and owner approval, privately create a **least-privilege project token** and put it in GitHub Actions repository secret `NEXUS_STAGE_D_RAILWAY_TOKEN`. No token is provisioned by this phase and project-token permission to read a Volume is still unverified. Use **Actions → NEXUS Stage D — Manual Encrypted Volume Capture → Run workflow** on `main`. It requires:

- `confirm_volume` — `cc47a350-6c7e-4487-89d9-c4b390f94884`
- `confirm_deployment` — `32cdcb2b-c03c-4a6f-b028-27a9977717ce` (only if still current)
- `confirm_runtime` — `9abbc067aad3ebbb0956432cf6682d2ea70e2824` (only if still current)
- `confirm_recovery_key` — the existing private-key proof acknowledgement, **only after** genuine owner-local proof
- `credential_scope` — `project` by default; the broader `workspace` path requires its separate explicit confirmation and separately scoped secret

**A human-input comparison is not cryptographic attestation of provider metadata.** It is a strong fail-closed anti-stale guard, but the operator can be mistaken or the deployment can change after the observation. The CLI's selected `volume files download /` command is a read-only copy, but it goes through the service and may be unavailable when the service is sleeping, when credentials lack privilege or when the plan is inactive. Do not restart/redeploy/attach a different service automatically if access fails. See [Railway CLI Volume](https://docs.railway.com/cli/volume) for provider command semantics.

On an independently authorized successful run, only ciphertext and a non-authoritative SHA receipt are uploaded to the expiring GitHub artifact; a fresh runner checks the bytes. The owner still has to **download and retain** the ciphertext outside Railway/GitHub, independently test decryption under their private key, restore the actual data into an isolated quarantined environment and get separate origin/atomicity/consistency validation before any production promotion. Seven-day artifact retention is not durable owner custody. No Seal, authenticated human pilot or release authority follows from the current code.

`A_out <= A_in`; original volume untouched. Issue #70 remains open.
