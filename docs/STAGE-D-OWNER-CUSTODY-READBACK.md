# Phase 35 — Owner-side, two-filesystem ciphertext readback

**State:** read-only verification utility and synthetic tests. The owner has not supplied a real offsite encrypted Stage D artifact, run-log anchor or recovery key. No real backup or live restore was performed by this change.

## Why

The manual-only Stage D workflow encrypts a private Railway volume capture as an OpenSSL CMS blob, anchors its hash in a GitHub Actions run log, and downloads the artifact again on a fresh runner. The short-lived artifact is not an independently retained owner backup. A second copy with a matching filename, or even matching receipt, is not sufficient: both copies must independently match the original run-log line and each other.

## Input and trust boundary

The operator must separately obtain the exact `NEXUS_ENCRYPTED_ESCROW_ANCHOR_V1` line from the authentic successful **manual Stage D workflow run** and independently verify the run's ID, attempt, commit and success in GitHub. This tool never contacts GitHub and cannot establish that the supplied log line is authentic. No GitHub token or Railway token is needed.

Place each downloaded encrypted **two-file pair** in an owner-controlled private directory on a separate mounted filesystem. The two exact filenames are `nexus-stage-d-private-capture.cms` and `nexus-stage-d-ciphertext-receipt.json`. Place the separately obtained run-log anchor line in a third private directory. All three directories must be canonical, owned by the executing operator and inaccessible to group/others; the individual files must be regular, single-link, owner-readable-only. Run this on a trusted POSIX host with appropriately enforced filesystem permissions, not Android shared storage.

Example (illustrative paths only):

```sh
chmod 700 /private/device-a /private/device-b /private/run-log
chmod 600 /private/device-a/* /private/device-b/* /private/run-log/anchor.txt
python3 scripts/verify-stage-d-owner-custody.py \
  --copy-a /private/device-a \
  --copy-b /private/device-b \
  --anchor-file /private/run-log/anchor.txt \
  --run-id '<exact-successful-github-run-id>' \
  --run-attempt '<exact-run-attempt>' \
  --commit-sha '<exact-40-hex-capture-workflow-commit>'
```

If the two directories are on the **same filesystem**, the tool refuses even if the contents match. Different `st_dev` values offer only a local filesystem separation signal; they do NOT prove separate physical machines, cloud providers, administrative domains, offsite location or independent retention. A bind mount to the same underlying data may be misclassified as separate by other schemes; the operator must establish actual separation outside this tool.

Exit 0 prints `TWO_FILESYSTEM_CIPHERTEXT_BYTES_MATCH` if both exact file pairs independently agree with the retained original run-log anchor and each other. Exit 2 prints a generic BLOCKED message without exposing paths, data, account metadata or tokens. There are no deletes, restores, uploads, mounts, deployments or HTTP calls.

## What remains before production promotion

1. Preserve real complete encrypted bytes and the authentic GitHub log anchor outside the seven-day GitHub artifact retention period. Confirm the manual capture actually ran and passed both uploader and independent artifact reread steps. A synthetic CI result does **not** count.
2. Independently establish owner possession of the matching **private** recovery key using the existing local challenge `scripts/verify-stage-d-recovery-key.py`. Do not paste that key, passphrase or plaintext here, or into CI.
3. Execute the existing `scripts/restore-stage-d-encrypted-escrow.py` on a trusted isolated host with the actual encrypted artifact, receipt and owner private key, and check the restored quarantine byte-for-byte. The readback implemented in this phase never decrypts and never restores.
4. Independently assess provider origin, absence of concurrent writers / snapshot atomicity, full data completeness, signed chain or recipient identity where applicable, current deployment SHA and complete exact-head CI. Obtain explicit operator approval before modifying the volume-bound Railway service.

**Every successful report deliberately retains** `production_backup_complete=false`, `off_provider_administrative_independence=not_proven`, `ciphertext_decrypted=false`, `deployment_authorized=false` and `authority=none`.

## Verification

```sh
python3 -m py_compile scripts/verify-stage-d-owner-custody.py scripts/test-stage-d-owner-custody.py
python3 scripts/test-stage-d-owner-custody.py
```

All fixtures are synthetic ciphertext-like bytes (NOT valid CMS and NOT Railway data). Their 'two different filesystem IDs' positive path is simulated to exercise only the gate logic; the unpatched same-filesystem path must fail. Production key custody, real encryption/decryption, independent offsite media, and live restored state are not tested here. No scripts or workflows are permitted to convert these tests into a release Seal. `A_out <= A_in`.