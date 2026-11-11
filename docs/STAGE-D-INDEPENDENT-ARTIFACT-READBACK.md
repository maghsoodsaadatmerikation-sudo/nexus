# Stage D — independent ciphertext artifact readback on a fresh GitHub runner

**State (2026-11-11): code and synthetic tests only. No original Railway Volume file has been downloaded and no real encrypted production artifact has been re-downloaded.**

## Why this stage is necessary

Earlier manual Stage D capture produced an OpenSSL CMS AES-256-GCM encrypted file and a strictly redacted receipt, wrote a non-secret SHA-256 anchor into its GitHub Actions job log, and uploaded two files as an expiring artifact. The upload step's success did **not** require a separately running job to retrieve the artifact and compare its actual stored bytes to the original log anchor. That left a delivery-integrity gap before owner custody and independent restore.

The manual workflow now contains a **mandatory** dependent job named `recheck-uploaded-ciphertext`, on a **fresh** Ubuntu GitHub runner, after the uploader job succeeds.

## Exact workflow contract

1. The existing exact original Volume UUID confirmation, private recipient-key acknowledgement, least-privilege Railway token choice, read-only CLI download and encrypted escrow remain unchanged. The provider credential exists in the one download step only.
2. Immediately after creating the AES-GCM ciphertext, the first runner prints the strict `NEXUS_ENCRYPTED_ESCROW_ANCHOR_V1` line to the original job log. Its fixed, non-secret line is also encoded as base64 into the first job's `anchor_b64` output. Only ciphertext digests, byte count, exact workflow/run/attempt/commit identifiers, original selected volume UUID, pinned public recipient fingerprint and explicit authority nonclaims are carried; **never** the ciphertext plaintext, Rust audit, tokens, or a private key.
3. The uploader's unique, immutable GitHub `artifact-id` becomes the `artifact_id` job output. No artifact selection by ambiguous filename or latest run.
4. The second job checks out the exact workflow commit without persistent checkout credentials, verifies zero ambient provider credentials, and uses the official SHA-pinned `actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093` (v4.3.0) to re-download **that specific artifact ID within the same workflow run**. It has no production Railway secret and no private recovery key.
5. `scripts/verify-stage-d-uploaded-artifact.py` rejects missing/extra files, directories, symlinks and hardlinks, invalid or noncanonical base64 handoff, mismatched run ID/attempt/SHA/artifact identifier, any invalid checksum or wrong receipt, unexpected schema or authority, and path substitution. It calls the existing strict offline log anchor verifier and rereads both files before returning.
6. The complete **manual workflow must fail** if readback/download/digest comparison fails. A passing second job only states `INDEPENDENT_RUNNER_CIPHERTEXT_BYTES_MATCH`, explicitly declaring that no decryption, external owner custody, provider-origin attestation, source atomicity, production backup, release authorization or Seal was proved.

No real provider download, artifact upload, or paid deployment is triggered by a PR. The new tests operate on synthetic random bytes, not real CMS payloads or NEXUS workspaces, and they cannot manufacture an actual operator proof.

## Synthetic negative cases

CI tests require an exact two-file artifact and correctly matched immutable run anchor, while refusing altered ciphertext even when the receipt was updated to match, harmless-looking receipt whitespace changes, modified Run/Attempt/Commit, missing or invalid artifact ID, malformed/noncanonical base64, duplicate/forged authority metadata, symlinked files, hardlinked files, extra subdirectories, and ambient Railway tokens. Static workflow-contract tests require both producer outputs, immutable artifact-ID downloader, a separate dependent runner, exact SHA pinning, and no provider credential passed to the verifier.

## Self-critique and remaining gates

This is an **independent runner readback**, not independently generated provenance: an attacker in the first capture process could lie about what was encrypted, write a forged original anchor and then upload consistently forged bytes. The independent job would still be internally consistent; it does not cryptographically sign the producer or validate what Railway actually served. GitHub storage remains temporary (currently 7-day retention), and the owner must preserve ciphertext and matching metadata elsewhere, validate the real private-key decryptability, independently inspect a full isolated restore, and witness an authenticated human pilot before Issue #70 can close.

The new job increases CI usage but requires no additional paid service, new hosted resource, production mutation, secret access, workflow dispatch, or human authority expansion. The existing explicit recovery-key check is still required. No release or Seal is authorized. `A_out <= A_in`.
