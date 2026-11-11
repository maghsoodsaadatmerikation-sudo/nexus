# Stage D — Offline encrypted escrow recovery (quarantined only)

**Status: implemented and tested on synthetic data; NO actual production
Railway Volume has been downloaded or recovered.** This is the receiving
half of the manual-only
[encrypted offsite capture workflow](../.github/workflows/stage-d-encrypted-volume-capture.yml).
It can be run in an **independent trusted Linux environment** with Python 3,
OpenSSL and the owner-held recovery key. It never contacts Railway, GitHub or
a production host.

## What this closes

PR #90 produced an encrypted `.cms` plus a **sanitized** JSON receipt using
OpenSSL CMS AES-256-GCM, without publishing the private RSA recovery key.
There was no end-user recovery CLI that could **validate, decrypt, examine and
privately restore** the resulting artifact. The new
[`scripts/restore-stage-d-encrypted-escrow.py`](../scripts/restore-stage-d-encrypted-escrow.py)
completes that offline local verification path.

Do not treat the availability of this tool as evidence of any existing
production backup: **the authenticated live Railway download has not run**,
and the connected Railway OAuth app cannot read Volume files or expose a
token to GitHub Actions.

## Private operator inputs

1. Download the `nexus-stage-d-encrypted-offsite-copy` artifact from the
   **actual manually dispatched** GitHub Actions run, if and only if it has
   completed successfully, within the artifact retention period (currently
   7 days). Extract the two exact files to a private directory, rejecting
   links and arbitrary paths: `nexus-stage-d-private-capture.cms` and
   `nexus-stage-d-ciphertext-receipt.json`.
2. Separately obtain the **owner-held private RSA key** corresponding to
   [the pinned public certificate](keys/stage-d-recovery-public-cert.pem).
   This key was NOT stored in GitHub. **Never paste it into ChatGPT, a PR,
   GitHub Secrets, an Actions job, Railway variables, logs or cloud agents.**
   If the key was not preserved by the owner, a future archive encrypted
   with that certificate may be unrecoverable. Generating a different key
   will NOT decrypt it.
3. Use a trusted **private Linux** environment with the repository checked
   out at a trusted revision, Python 3 and OpenSSL. No Railway credentials
   are needed to restore a previously captured off-provider artifact.
   The target parent must be a canonical, private `0700` directory,
   owned by the current user, outside the repository. The key must be a
   regular, unlinked owner-only file (`0600` or `0400`).

Example (replace the private paths with existing local files; **no** real
capture is included in this repository):

```bash
umask 077
mkdir -p "$HOME/nexus-recovery-private"
chmod 700 "$HOME/nexus-recovery-private"
chmod 600 /private/owner-held-recovery-private-key.pem

python3 scripts/restore-stage-d-encrypted-escrow.py \
  --ciphertext /private/nexus-stage-d-private-capture.cms \
  --receipt /private/nexus-stage-d-ciphertext-receipt.json \
  --private-key /private/owner-held-recovery-private-key.pem \
  --destination "$HOME/nexus-recovery-private/quarantined-restored-data"
```

**Only a successful, fully verified invocation creates the destination.**
The directory is published with Linux atomic `renameat2(RENAME_NOREPLACE)`;
an existing target must never be overwritten or merged. It contains supported
workspace JSON files, a `requests/` marker directory and the mandatory
`.nexus-recovery-required` quarantine marker. It does not resume requests,
start NEXUS or write to Railway. Do not remove the quarantine marker.

## Exact checks performed *before* publishing

- Reject symlink/hardlinked/oversized inputs, unsafe private-key permissions,
  nonprivate target parent, existing targets, files in the public checkout,
  and untrusted recipient certificate bytes.
- Enforce the exact, versioned sanitized receipt schema, SHA-256, ciphertext
  byte length, fixed public certificate digest, and explicit
  `release_authorized=false`, `seal=false`, `authority=none`.
- Invoke OpenSSL CMS decryption with a reduced credential-free subprocess
  environment; refuse any unsuccessful AES-GCM authentication. Feed OpenSSL
  **the exact immutable ciphertext bytes already SHA-256 checked** through
  stdin, rather than reopening a possibly swapped file path. After isolated
  restore, independently reread both the encrypted input and its receipt:
  any post-hash substitution blocks publication. No output is published
  until OpenSSL exits **successfully**, so partially decrypted plaintext
  cannot be mistaken for authentic evidence.
- Parse the plaintext TAR **in memory**, without extracting TAR paths.
  Require exactly the three fixed regular files (one each), size limits,
  no duplicate names, no symlink, no hardlink, no unexpected PAX data.
- Require the original private intake and capture receipts' exact
  versioned nonclaims, pinned Railway IDs, same archive SHA-256 and file
  count. Reject any attempted escalation of backup status, Rust audit,
  atomic-source consistency, release or Seal.
- Validate every file in the `nexus.data-snapshot.v1` archive through the
  existing bounded snapshot validator. Restore to a **new temporary
  quarantine** in the private target parent, then independently compare
  every restored byte and exact file/directory set with its archive,
  including the quarantine marker.
- Atomically publish only the validated quarantined directory.
  Temporary plaintext files are removed on exit (best-effort filesystem
  deletion, **not** a guarantee of secure erasure from disks, snapshots,
  swap or compromised hosts). Stdout/stderr never includes workspace
  content, private paths or provider tokens.

## Threat boundaries and self-critique

A successful `OFFLINE QUARANTINED RESTORE: PASS` proves **only**:
the locally supplied CMS decrypts under the matching operator private key,
the encrypted bytes pass their GCM authentication check, a matching declared
receipt and structurally valid NEXUS archive are present, and an isolated
private quarantine restores the archived bytes.

**Not proven:** the public encryption certificate has *no signing authority*;
anyone with it can encrypt forged but correctly formatted evidence. AES-GCM
protects the decrypted payload against alteration **relative to that
encryption**, but does NOT establish Railway provider provenance, authorized
operator identity, complete production capture, point-in-time consistency,
independent private-key custody, live server recovery, or a valid Seal. The
capture receipt still states `provider_file_origin` unverified and
`independent_complete_production_backup` not proven.

The offline restore utility requires Linux's atomic no-replace rename;
Android/Termux and other operating systems have **not** been independently
qualified for this specific syscall. Do not assume that a mobile browser
alone can decrypt CMS or restore the archive. If the required platform is
unavailable, the output must be **BLOCKED**, never silently published via an
unsafe rename. A test-only synthetic check does not count as a real
user-held off-provider copy.

An encrypted artifact has **7-day GitHub retention** and GitHub Actions
storage is not sufficient proof of owner-controlled durable custody. The
owner must preserve the encrypted archive and receipt, verify their checksums
on independent private storage, and prove real data recovery with a separately
witnessed operation. Never upload plaintext, keys or recovered workspace
data to CI/artifacts, this conversation or an Issue.

No release authorization, production deployment, volume mutation or
human first-user acceptance follows from this step.
[Issue #70](https://github.com/maghsoodsaadatmerikation-sudo/nexus/issues/70)
remains OPEN. `A_out <= A_in`.
