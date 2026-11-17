# Phase 40 — Offline owner-held encrypted backup restore kit

**Goal:** provide a narrowly scoped, executable offline recovery package suitable for a trusted private Linux host and potentially for Termux, without requiring a full NEXUS checkout, Railway CLI or new paid infrastructure. This stage does **not** obtain real production data, owner private keys, matching certificates or decrypt an actual Stage D backup.

## What is shipped

Workflow: [NEXUS Stage D Offline Owner Quarantined Recovery Kit](https://github.com/maghsoodsaadatmerikation-sudo/nexus/actions/workflows/stage-d-phone-restore-kit.yml). The CI produces an SHA-256 reported ZIP containing **exactly nine public items**: the reviewed offline recovery script, the bounded NEXUS data-snapshot reader, the reviewed credential-scope helper, the pinned public RSA certificate, two **constants-only** import adapters, a shell launcher, a README, and a source-bound manifest. The adapters preserve the original volume/deployment/commit and encryption-envelope constants **without including the Railway capture/CLI or encryption/upload implementation**. Any source-pinned constant change blocks packaging until reviewed. No private key, token, .cms file, user conversation or workspace copy goes into this artifact.

The source is `scripts/build-stage-d-phone-restore-kit.py`; the automated acceptance is `scripts/test-stage-d-phone-restore-kit.py`. The workflow is public-source-only with `contents: read`, SHA-pinned checkout, no Railway secrets, a pure reproducible ZIP and an external .sha256 sidecar. The manifest is self-declared and **not an independent cryptographic signature or proof of GitHub-run authenticity**. Obtain a successful exact-source run through GitHub directly, not a stranger-supplied archive.

## Using the tool, only with legitimate private owner-held material

On a trusted Linux installation, install Python 3 and OpenSSL. Termux on Android may install them with `pkg install python openssl unzip`, but physical-device compatibility, package trust and kernel support have **not** been verified. After downloading the ZIP from the reviewed GitHub workflow, extract it into an owner-only private directory outside Git. Do not extract into shared Downloads or a synced cloud location when working with confidential inputs. The *package itself* contains no private material.

**The owner must already possess three separate genuine input files**: (1) the exact `.cms` produced by the manual encrypted capture workflow, (2) its `.json` receipt, (3) the matching privately held original RSA key. The user must obtain the original GitHub run-log anchor independently and retain another encrypted copy on independent controlled storage. The existing Phase 39 kit can check the key against the pinned certificate first; it cannot invent or recover a missing key.

```sh
pkg install python openssl unzip
cd "$HOME"
unzip /PRIVATE/LOCATION/nexus-stage-d-owner-offline-restore.zip
cd nexus-stage-d-offline-recovery
mkdir -m 700 -p "$HOME/private-output"
./restore-local.sh \
  "$HOME/private-inputs/nexus-stage-d-private-capture.cms" \
  "$HOME/private-inputs/nexus-stage-d-ciphertext-receipt.json" \
  "$HOME/private-key-dir/existing-matching-private-key.pem" \
  "$HOME/private-output/new-quarantined-restore"
```

Paths must be absolute and canonical. The destination must **not** exist and its parent must belong to the current owner with 0700-like private permissions. The private RSA key must be an owner-only 0600 regular single-link file; sharing it with ChatGPT, GitHub Actions, issues or Railway is forbidden. The tool will not create a new private key. The local script refuses a mutated ciphertext, mismatched receipt, untrusted certificate, wrong key, unsafe paths, existing destination, invalid snapshot records, or a platform without the required atomic no-overwrite directory publication. Any failure must stay BLOCKED; never drop those checks to force success.

**Privacy implications:** Although the tool has no network client and explicitly removes provider credentials from OpenSSL subprocesses, successful recovery creates *plaintext private workspace files* on the owner's local filesystem, quarantined under `.nexus-recovery-required`. A private encrypted phone backup and a private restored plaintext directory are different custody risks. Sensitive NEXUS workspaces should only be recovered onto a personally trusted and suitably secured machine. Deletion of temporary files is best effort, not secure erasure from snapshots, swap or compromised devices.

## Tests and limitations

- The real original recovery code in the extracted package is tested in disposable Ubuntu Linux CI with **real OpenSSL AES-256-GCM CMS encryption/decryption** and a new ephemeral **synthetic** RSA keypair/certificate. The exact distributed public certificate is only replaced in the isolated CI extraction for the synthetic exercise; the shipped ZIP keeps the fixed reviewed public certificate hash.
- Synthetic tests also reject ciphertext tampering, unsafe private-key permissions, existing target, archive alteration, unexpected private-key member, bad source commit and unsafe output overwrite. The normal repo's complete offline recovery and environment-scoping tests run as regressions.
- The previously hardcoded `/usr/local/bin:/usr/bin:/bin` subprocess PATH made Termux decryption fail to resolve OpenSSL. This phase adds the fixed standard Termux OpenSSL directory **only for explicitly opted-in offline decrypt**, never for authenticated Railway CLI, source validator or other subprocesses. That does not certify arbitrary Termux distributions; if the platform or renameat2 support is missing, BLOCK.
- The pinned Stage D deployed source and volume identities reflect the latest previously observed Railway revision, **not an independent witness of provenance at the time of an actual capture**. If Railway is subsequently redeployed, the pin must be reconciled before generating and running new capture; do not silently associate artifacts with historical runtime IDs.

Even an actual successful owner-local restore proves only that the **supplied** ciphertext/receipt could be authenticated, decrypted and restored as a structurally valid isolated quarantined copy. It does not prove that the ciphertext originated from Railway, was captured atomically, includes the complete latest production state, is maintained on independent storage, can survive a live production redeploy or authorizes NEXUS to run. Stage D production cutover and Issue #70 remain blocked until independently witnessed original provider capture, owner custody, real isolated restore, live operational testing and explicit release authorization are satisfied. Original Railway `/data` is untouched; no settings patch was committed. `A_out <= A_in`.
