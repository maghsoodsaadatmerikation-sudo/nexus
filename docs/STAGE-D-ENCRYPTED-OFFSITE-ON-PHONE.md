# Stage D — گوشی به‌جای رایانه، GitHub Actions به‌جای میزبان جدید

**Status: cloud workflow implemented, LIVE OFF-PROVIDER BACKUP NOT YET EXECUTED.**
No real Railway volume data, credentials, or workspace exports are committed to
this repository. The original `/data` service and volume remain untouched.

## Practical architecture

The manual-only workflow
[`stage-d-encrypted-volume-capture.yml`](../.github/workflows/stage-d-encrypted-volume-capture.yml)
runs on a temporary GitHub-hosted Ubuntu runner, not on the owner's phone.
The owner needs a signed-in phone browser for GitHub and Railway settings,
**not a local Linux/Rust/Docker installation**.

Workflow gate:

1. Manually choose **Actions > NEXUS Stage D — Manual Encrypted Volume Capture >
   Run workflow**, branch `main`. Enter the **exact** original Volume UUID
   `cc47a350-6c7e-4487-89d9-c4b390f94884`. It is never auto-run on
   `push`, `pull_request`, schedules or deployments.
2. Before starting, the user must privately configure a Railway credential in
   GitHub repository **Settings > Secrets and variables > Actions > New
   repository secret**, named **`NEXUS_STAGE_D_RAILWAY_TOKEN`**. Never paste
   its value into ChatGPT, issues, comments, commits, Actions inputs or source
   files. A Railway project token is preferable to a broader account token,
   **but CLI permission to download volume files with a project token is NOT
   verified**; if refused, stop and review instead of automatically widening
   authority.
3. Job checks the exact original target and public recipient certificate,
   downloads SHA-256-pinned Railway CLI v5.71.0 without a token, and passes the
   credential only to the existing exact-target **READ-ONLY**
   `volume files download /` operation. No provider upload, delete, detach,
   redeploy, restart, resume or live restore.
4. `capture-railway-volume-readonly.py` validates every copied supported
   workspace and request ledger file, produces a single bounded private
   snapshot JSON and quarantined structural restore under a temporary runner
   directory. Unsupported files or identity drift BLOCK the job. A successful
   local copy alone does **not** establish an atomic source point in time.
5. The independent `stage-d-encrypted-escrow.py` rereads exact child
   evidence, validates the parent capture receipt with no forged authority
   fields, pins the recipient X.509 certificate and AES-256-GCM-encrypts an
   archive containing **only** the validated snapshot JSON and two private
   structural receipts. Plaintext is not included in the uploaded artifact.
6. GitHub uploads exactly a `.cms` ciphertext and a generic checksum/claim
   receipt; ciphertext is kept for **seven days** unless deleted sooner.
   Cleanup attempts to remove plaintext scratch even on a failed run.
   Download the encrypted artifact privately from the completed workflow and
   preserve the **separate private recovery key** outside GitHub/Railway.
   The private key was delivered separately to the owner and is **never**
   committed or uploaded to the CI runner.

### Public-only encryption identity

Recipient: `docs/keys/stage-d-recovery-public-cert.pem`.
Exact certificate **file SHA-256**:

`b27cc7a84e333fce78f790dce20335258b11e724bac1a91b3b7c886ac3812091`

The private key is NOT in GitHub. If it is lost, the encrypted artifact is
unrecoverable. Do not upload it into Railway, GitHub Issues, or any public
storage location. The generated private key is not hardware-protected or
provider-attested. Save two separate private copies.

### Offline decrypt + isolated restore (NOT PERFORMED ON REAL DATA)

On a trusted environment that has `openssl`, `tar`, Python, the private
key and downloaded ciphertext, decrypt without publishing any contents:

```bash
umask 077
mkdir -p /private/nexus-offline-capture
openssl cms -decrypt -inform DER \
  -in /private/nexus-stage-d-private-capture.cms \
  -recip docs/keys/stage-d-recovery-public-cert.pem \
  -inkey /private/nexus_stage_d_recovery_private_key.pem \
  -out /private/nexus-offline-capture/package.tar
tar -tf /private/nexus-offline-capture/package.tar
```

**Before extracting:** require exactly these three ordinary relative entries,
no absolute names or symlinks: `nexus-private-data-snapshot.json`,
`intake-report.json` and `capture-receipt.json`. On a clean separate
private directory, extract only those fixed names. Then:

```bash
mkdir -p /private/nexus-offline-capture/evidence
tar -xf /private/nexus-offline-capture/package.tar \
  -C /private/nexus-offline-capture/evidence \
  nexus-private-data-snapshot.json intake-report.json capture-receipt.json
python3 scripts/data-snapshot.py inspect \
  /private/nexus-offline-capture/evidence/nexus-private-data-snapshot.json
python3 scripts/data-snapshot.py restore \
  /private/nexus-offline-capture/evidence/nexus-private-data-snapshot.json \
  /private/nexus-quarantined-restore --offline
```

The restore target must **not exist** before executing restore. Never call
`resume`, switch mounts, or attach the isolated restored data to a public
service without separate verified operational evidence. Verify private
checksums and restored file bytes independently.

## Self-critique / remaining gate

- The connected Railway OAuth tool can see only the **names** of secrets
  (including `NEXUS_API_TOKEN`), and exposes no private Volume file read,
  list, or download API. Therefore the model cannot inject a Railway login
  into this workflow, execute a real capture from chat, or claim this was
  done. An explicit operator-supplied repository secret is required.
- No-charge status is **not guaranteed**: GitHub Actions private-repository
  minutes/storage, Railway volume egress, and the Railway account plan may
  involve charges. The workflow is **manual only**, is bounded to one run,
  and does not auto-consume those resources.
- GitHub artifact custody is off Railway, but GitHub is not automatically a
  long-term secure custodian; the workflow artifact expires in seven days.
  The owner must save its ciphertext and private key elsewhere. The
  transient runner holds plaintext while processing, within its short-lived
  environment, not on the user's device. Treat provider trust accordingly.
- CMS AES-256-GCM detects ciphertext alteration **at decryption**, but this
  does not cryptographically attest which Railway Volume produced the copy.
  A read-only directory download is not a provider-atomic snapshot if live
  writers change data. A successful CI run is **not** independent origin,
  point-in-time consistency, an authenticated live restore, a first-human
  workflow, release authority or Seal.
- The workflow deliberately runs no real operation without an explicit
  original-Volume confirmation, the owner-created secret and a **manual
  trigger**. If unavailable, stop with **BLOCKED** rather than falling back
  to a broader token or a public endpoint. `A_out <= A_in`.

See also [Issue #70](https://github.com/maghsoodsaadatmerikation-sudo/nexus/issues/70)
and [Stage D private intake](STAGE-D-PRIVATE-EXPORT-INTAKE.md).
