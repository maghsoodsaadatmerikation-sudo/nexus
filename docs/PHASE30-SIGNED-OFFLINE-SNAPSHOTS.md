# Phase 30 — opt-in offline Ed25519 signatures for NEXUS snapshots

## Security improvement and explicit boundary

Phase 29 verified that synthetic snapshot bytes could move between separate
GitHub Actions runners, but SHA-256 pins passed by the same GitHub workflow
cannot authenticate the person or system publishing a backup. Phase 30 adds
`scripts/nexus-operator-snapshot-signature.py`, an **offline, opt-in**
detached Ed25519 signature, exact signer-key fingerprint requirement and
signed-restore command. The private signing key is never part of a snapshot,
restored workspace, artifact or printed JSON report.

A valid signature proves possession of an Ed25519 private key corresponding
to an **independently approved public key fingerprint**. It does **not**
establish a legal/person identity, independent organizational custody, that
the key was never stolen, that a snapshot is the newest one, or that a host
was uncompromised. Even with a valid signature, the existing full snapshot
ZIP/manifest/journal checks and anti-replay state are required.

**Important:** This new command does not turn off the older unsigned
`nexus-operator-snapshot.py restore` path. Requiring signatures throughout
a deployment would need a separate reviewed policy/enforcement migration.
Do not describe the overall backup system as publisher-authenticated.

## Offline operator procedure (illustrative, no real keys in CI)

On a trusted offline Linux machine as an unprivileged user, provision a
dedicated private Ed25519 signing key and a public key. Keep the private
directory 0700, and the private PEM 0600. For example:

```bash
umask 077
mkdir -m 700 /path/to/private-key-directory
openssl genpkey -algorithm Ed25519 \
  -out /path/to/private-key-directory/producer-private.pem
chmod 600 /path/to/private-key-directory/producer-private.pem
openssl pkey -in /path/to/private-key-directory/producer-private.pem \
  -pubout -out /path/to/approved-public.pem
```

Independently distribute and verify the expected SHA-256 fingerprint of the
**32 raw Ed25519 public-key bytes**, not the SHA-256 of the PEM text. A
one-time fingerprint calculation on an independently trusted machine is:

```bash
python3 - <<'PY'
import hashlib
from pathlib import Path
from cryptography.hazmat.primitives import serialization
p = serialization.load_pem_public_key(Path("/path/to/approved-public.pem").read_bytes())
print(hashlib.sha256(p.public_bytes(
    serialization.Encoding.Raw,
    serialization.PublicFormat.Raw)).hexdigest())
PY
```

First stop the operator service and use the existing offline exporter.
Independently capture its `snapshot_sha256` and `workspace_sha256` report
values; do not use the ZIP itself as the only trusted digest source. Set
`ARCHIVE_SHA256`, `WORKSPACE_SHA256` and `TRUSTED_SIGNER_SHA256` to the
reviewed values. The workspace example below is `acceptance`.

```bash
python3 scripts/nexus-operator-snapshot-signature.py sign \
  --archive /private/transfer/snapshot.zip \
  --expected-archive-sha256 "$ARCHIVE_SHA256" \
  --workspace acceptance --expected-workspace-sha256 "$WORKSPACE_SHA256" \
  --signature /private/transfer/signature.json \
  --private-key /path/to/private-key-directory/producer-private.pem \
  --expected-signer-sha256 "$TRUSTED_SIGNER_SHA256" \
  --approve-offline-sign
```

Transport the ZIP, detached signature and public PEM over separately
controlled channels if possible. **Never** transport the private PEM.
The recipient pins the expected public-key fingerprint independently of
the sender's archive/signature and verifies before any restore:

```bash
python3 scripts/nexus-operator-snapshot-signature.py verify \
  --archive /private/transfer/snapshot.zip \
  --expected-archive-sha256 "$ARCHIVE_SHA256" \
  --workspace acceptance --expected-workspace-sha256 "$WORKSPACE_SHA256" \
  --signature /private/transfer/signature.json \
  --public-key /path/to/approved-public.pem \
  --expected-signer-sha256 "$TRUSTED_SIGNER_SHA256"
```

Only after **explicit operator approval** is recovery allowed into a new,
empty, owner-private root:

```bash
python3 scripts/nexus-operator-snapshot-signature.py restore \
  --root /private/new-empty-root \
  --archive /private/transfer/snapshot.zip \
  --expected-archive-sha256 "$ARCHIVE_SHA256" \
  --workspace acceptance --expected-workspace-sha256 "$WORKSPACE_SHA256" \
  --signature /private/transfer/signature.json \
  --public-key /path/to/approved-public.pem \
  --expected-signer-sha256 "$TRUSTED_SIGNER_SHA256" \
  --approve-offline-restore
```

The CLI rejects duplicate JSON fields, malformed/unpinned signatures,
mismatched archive/workspace pins, unsafe final-component symlinks and
hardlinked files, existing detached-signature destinations and missing
explicit approval. The signed-restore route calls the existing full
ZIP/content/journal validator before writing, and the existing snapshot
restorer rechecks the archive SHA and the empty-root rule. A failed
signature is inert: no destination is created.

## Verification

`.github/workflows/operator-signed-snapshot.yml` runs pinned Python
cryptography and pytest versions on a disposable unprivileged GitHub runner.
It creates an **ephemeral synthetic signing key**, signs only synthetic
operator data, verifies the approved key pin, restores a complete consumed
approval journal and checks that the approval cannot be replayed. Negative
tests reject changed content, changed signed context, bad keys, altered
signatures, duplicate fields, key-file permissions and overwrite attempts.
The tests do not distribute or authenticate any real publisher secret.

**Not proven:** encrypted confidentiality, independent verified publisher
identity, signed freshness/anti-rollback, host isolation from a hostile
same-UID writer, separate durable backup provider, production disaster
recovery, unattended operator jobs, a public Docker service or user-visible
model autonomy. A valid old signed snapshot can still be replayed into a
new empty root without an independent trusted latest-checkpoint policy.

This work is stacked on draft PR #244, remains unmerged/undeployed until
the exact-head CI and security acceptance pass, and grants no additional
NEXUS execution authority. Maintain `A_out <= A_in`.
