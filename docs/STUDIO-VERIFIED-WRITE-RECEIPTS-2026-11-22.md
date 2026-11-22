# NEXUS — confirmed write receipts (draft)

This patch strengthens **reviewed GitHub write-result claims** rather than expanding the list of automatically executable tools.

For an explicitly approved branch creation, the gateway now requires a fresh provider GET of the exact branch ref and reviewed head after the creation response. For `already_exists`, it verifies the ref without claiming a new branch was created. For an explicitly approved file commit, it now requires a *second, separate observation* of the branch head plus the exact non-symlink file content at the returned commit. Git tree/blob SHA and complete UTF-8 bytes must match the reviewed draft.

Only after those follow-up observations does the gateway return a bounded `receipt` with the reviewed operation, outcome, observation method and `confirmed_by_followup_provider_read=true`. The receipt explicitly states `independent_attestation=false`, `deployment_verified=false`, and `authority=none`: a response from the same provider is evidence of persistence, **not cryptographic or third-party attestation**. No credentials, original prompt, file text or secret targets are included in the receipt.

A failed/mismatched follow-up observation returns **409 unconfirmed**. This does **not** prove the mutation did not occur; users must inspect the remote repository before another attempt. The gateway never retries a write on its own. The branch write and file commit endpoint contracts and FastAPI tests are updated. UI and synthetic Chromium fixtures must be updated to accept and strictly validate the new receipt before promotion.

This PR is stacked, remains draft, and each commit has `[skip render]`; no public deployment or GitHub user-account write is initiated by this patch.
