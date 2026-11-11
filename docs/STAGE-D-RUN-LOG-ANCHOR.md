# Stage D — GitHub run-log ciphertext anchor (no paid attestation)

**Status: offline/synthetic-tested mechanism; no real production Volume download.**
This is a narrow independent *file-substitution detection* aid for the
[manual encrypted Volume capture](../.github/workflows/stage-d-encrypted-volume-capture.yml)
and the [private offline recovery](STAGE-D-ENCRYPTED-OFFLINE-RECOVERY.md).
It does **not** supply a release Seal, backup origin guarantee or signed
provider attestation. Issue #70 stays open.

## Why GitHub's signed Artifact Attestations were not chosen

GitHub's current [artifact-attestation eligibility
documentation](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations)
says GitHub Free/Pro/Team attestation is limited to public repositories.
Private/internal repositories require Enterprise Cloud. NEXUS is a private
repository and the operator requires a zero-extra-budget path. We therefore
**do not** silently add an expensive Enterprise Cloud dependency.

This is instead an **ordinary GitHub Actions job log** recorded by GitHub.
The log is an authenticated audit observation *if the operator retrieves it
from the actual GitHub repository and completed-success workflow run*;
the line itself has **no digital signature** and can be copied or forged
outside GitHub. The verifier is offline, not an independent log authenticator.

## What the manual capture workflow now records

After the existing exact-target read-only capture and AES-256-GCM encryption,
and **before** uploading the ciphertext-only Actions artifact, the workflow
runs:

```bash
python3 scripts/stage-d-run-log-anchor.py emit \
  --encrypted-dir "$RUNNER_TEMP/nexus-stage-d-encrypted"
```

The script independently reads the two fixed output files with no-follow,
single-link, bounded reads; rechecks the complete strict sanitized receipt;
compares its SHA-256 and ciphertext length with the ciphertext; requires
GitHub Actions environment `workflow_dispatch`, `main`, the exact NEXUS
repository and expected workflow ref, a valid SHA and numerical run ID and
attempt; then re-reads both files before printing **exactly one**
`NEXUS_ENCRYPTED_ESCROW_ANCHOR_V1` line.

The logged JSON contains **only** the workflow/repo ref, GitHub run ID,
attempt number, commit SHA, original selected Volume UUID, ciphertext
SHA-256 and byte count, exact receipt SHA-256, public recipient certificate
fingerprint, and explicit **no provenance, no release authority** status.
It contains **no source workspace IDs or content, raw archives, credential
values, RSA private key, personal paths, or decrypted data**. The anchor
step itself gets no Railway token environment.

### How the operator checks a future real run

1. Privately sign in to the trusted GitHub account, locate the **specific**
   completed-success `NEXUS Stage D — Manual Encrypted Volume Capture` run,
   open its job log and confirm the run ID/attempt and the actual workflow
   commit shown in the GitHub UI. A pasted or forwarded line is **not proof**.
   If there is no successfully completed manual run, stop.
2. Copy the single **line beginning with**
   `NEXUS_ENCRYPTED_ESCROW_ANCHOR_V1 ` from the original job log into a
   private plaintext file. Remove any GitHub UI timestamp or log decoration.
   This file contains only non-secret hashes/metadata.
3. Download the actual ciphertext-only artifact from that same run before
   GitHub's 7-day retention expires. Safely unpack only the two intended
   files to a private directory; reject symlinks, hardlinks and extra files.
4. Compare the anchored logs with the artifact using the same trusted
   repository commit, with **IDs taken independently from the verified
   GitHub UI**. Example, in a trusted local/offline Linux environment:

```bash
python3 scripts/stage-d-run-log-anchor.py verify \
  --encrypted-dir /private/nexus-encrypted-artifact \
  --anchor-file /private/verified-original-github-log-line.txt \
  --expected-run-id 123456789 \
  --expected-attempt 1 \
  --expected-sha 0123456789abcdef0123456789abcdef01234567
```

The numbers/SHA above are **illustrative only**, not a real or current
NEXUS run ID. **Do not copy them into production recovery.** A successful
`LOG_ANCHOR_LOCAL_FILE_MATCH_ONLY` means only that the two *local* files
match the specified log line's digests and conservative schemas; it
explicitly reports `github_job_success=not_independently_checked` and
`authentic_log_origin=operator_must_check_in_github`.

Only after this independent run-log comparison should the operator proceed
with the **owner-held private key** and
[offline quarantined restore](STAGE-D-ENCRYPTED-OFFLINE-RECOVERY.md).
The private key must NEVER be placed into GitHub Actions or the log check.

## Tests and self-critique

`scripts/test-stage-d-run-log-anchor.py` uses disposable synthetic
RSA/CMS AES-GCM evidence to verify exact anchor generation and offline
matching, a different run ID/attempt/SHA, invalid event/workflow/ref,
malformed run identifiers, ciphertext replacement (even when the JSON
receipt is edited to match), receipt replacement, extra/duplicate fields,
forged release authority, symlink/hardlink substitution and absence of
ambient secrets and workspace bytes from logged output.

**Limits:**

- GitHub log provenance is platform-authenticated **only when independently
  viewed from GitHub**; the copied line is not cryptographically signed.
  The offline script cannot verify GitHub's TLS authentication, Actions
  job conclusion or account authorization. A malicious operator could
  intentionally copy a fabricated line.
- A successful log anchor is printed **before** the encrypted-artifact
  upload. If upload or the whole run later fails, an anchor may still
  exist; require the actual job conclusion to be SUCCESS. The scripted
  verifier alone does not establish artifact upload success.
- Cryptographic hashes bind bytes **between that log and that artifact**,
  but do not prove what the Railway CLI fetched, whether the provider
  identity was independently attested, whether a live volume was
  quiescent/atomic or whether a complete durable recovery is possible.
- This mechanism neither verifies the private-key holder nor upgrades
  the receiving offline-restorer's schema/authority. A successful
  synthetic test **is not a live backup**.
- No new services, billing, token access, credentials, provider mutation,
  deployment, or production-volume reads were performed in this stage.

**Keep `A_out <= A_in` and Issue #70 OPEN** until the owner-authorized
authenticated capture runs, encrypted bytes are privately preserved outside
GitHub retention, and a separate real authenticated restore and human
acceptance are witnessed.
