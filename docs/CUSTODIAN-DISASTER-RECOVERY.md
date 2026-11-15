# Receiver disaster recovery: independently pinned signed history

The separate NEXUS witness receiver (see [Independent Witness Custodian](INDEPENDENT-WITNESS-CUSTODIAN.md)) now supports **operator-controlled export and restore of its signed acknowledgment history**. This is a read-only public-metadata backup, **not a private-key backup, not an external deployment and not an immutable retention service**.

## Loss model and invariants

A recipient host may lose its entire private receiver-ledger directory, while the *latest acknowledged receipt* and a full backup of the signed chain survive under a separate operator's custody. The restored receiver must retain its original receiver identity, pinned public keys, exact signature chain, and most recent independently acknowledged sequence. An incomplete, rewritten, old or forged backup must not restore an apparently valid receiver.

The CLI `scripts/workspace-witness-recovery.py` has two strict operations:

- `export`: opens an existing private receiver directory with the same POSIX lock as admissions, revalidates *all* original source and receiver Ed25519 signatures, checks the independently supplied **latest** signed acknowledgment and pinned public key identities, then writes one exclusive fsynced backup outside the receiver directory. **No signing key or SSH identity is exported.**
- `restore`: validates a bounded backup (schema, cryptographic SHA-256 of exact canonical state, final receipt digest and entire signed event/acknowledgment chain), verifies the separately retained latest package against explicitly chosen **trusted public keys, expected receiver ID and minimum sequence**, and creates a *new, previously nonexistent* private receiver directory. It never overwrites or silently resets a damaged deployment. Verification failures occur **before** creating the recovery directory.

**The externally retained latest acknowledgment is the recovery anchor**, not a package found inside the missing/recovered receiver state. An operator must preserve the **minimum accepted sequence** in a separate trust domain, and independently source and pin the receiver/source public keys. A valid but stale backup is not fresh; only an exact match to the latest independently retained acknowledgment can pass. If that external receipt is missing, or a signing key has been compromised, do not bypass these conditions.

## Offline operator procedure

The following paths are illustrative. Run the receiver as a dedicated separately controlled user on a private POSIX filesystem. First export when the **recipient's actual latest acknowledged package** is independently available from controlled storage or authenticated communications:

```sh
python3 scripts/workspace-witness-recovery.py export \
  --store /private/nexus-custodian \
  --backup /independent-backups/custodian-history-000042.json \
  --trusted-checkpoint /independent-retention/latest-ack-000042.json \
  --expected-receiver-id external-organization-1 \
  --trusted-source-key-id rollback-2026-a \
  --trusted-source-public-key /trusted/rollback.pub.pem \
  --trusted-ack-key-id custodian-2026-a \
  --trusted-ack-public-key /trusted/custodian.pub.pem \
  --minimum-sequence 42
```

Copy the backup to physically and administratively independent storage with documented acknowledgment, integrity and retention controls. The backup contains **signed receipts, acknowledgment signatures, public keys, hashes and counts only**; this metadata can still correlate operator activity. Treat it as confidential operational data. Never place real user conversation data, API tokens or private keys in that backup.

After host failure, provision a **new** private receiver environment. Separately recover the receiver's private Ed25519 acknowledgment key through an approved encrypted key-custody process (this script intentionally does not provide one). Validate the signatures and recipient identity **before** restoring:

```sh
python3 scripts/workspace-witness-recovery.py restore \
  --new-store /private/new-nexus-custodian \
  --backup /independent-backups/custodian-history-000042.json \
  --trusted-checkpoint /independent-retention/latest-ack-000042.json \
  --expected-receiver-id external-organization-1 \
  --trusted-source-key-id rollback-2026-a \
  --trusted-source-public-key /trusted/rollback.pub.pem \
  --trusted-ack-key-id custodian-2026-a \
  --trusted-ack-public-key /trusted/custodian.pub.pem \
  --minimum-sequence 42

python3 scripts/workspace-witness-custodian.py latest \
  --store /private/new-nexus-custodian
```

Then authenticate the restored **latest** package independently with
`workspace-witness-custodian.py verify-package`. Confirm the receiving SSH account, pinned host key, fixed command policy and independently held signing private key **before** resuming new acknowledgments. A successfully restored public history is **not sufficient** to assert that signing-key custody or the host's SSH identity has been restored safely. A new host key requires a reviewed out-of-band pinning ceremony; never silently accept it through SSH.

## Security boundaries

- Exported backup hashes help detect accidental corruption; the actual source and receiver **Ed25519 signatures** and the independently retained newest signed checkpoint establish integrity and continuity. A hash stored beside its payload *alone* is not an external trust anchor.
- The backup is **not encrypted**: it contains public cryptographic metadata and identifiers. Encrypt it at rest when recipient policy requires, with keys managed outside NEXUS.
- The receiver's signer private key is **never** backed up or restored by this tool. A missing, different or revoked private key must block fresh receipt issuance; rekeying requires its own independently approved protocol.
- Operator-level rollback of *both* backup and external checkpoint, key compromise or corruption of the external independent storage remains out of scope. Pin the latest sequence with the other trust domain.
- The tested recovery is local and synthetic. No external host, WORM storage, cloud bucket, independent administrator, real incident, production key, TLS/SSH service or deployment has been provisioned by this PR.
- No automatic import of external machine histories is enabled. NEXUS gateway continues to deny unattested machine-history import.

## Acceptance evidence

`scripts/test-workspace-witness-recovery.py` constructs disposable genuine Ed25519 keypairs, multiple signed states and a separately retained latest package. It tests full original receiver directory loss, exact restore and continuation of receipt sequence, stale signed backups, wrong trusted keys, altered or truncated history, SHA-256 tampering, unknown fields, double JSON keys, symlinks/hardlinks, concurrent restore race, and no signing key in the backup.

`scripts/test-workspace-witness-ssh-real.py` now extends its **real loopback OpenSSH** handshake and post-commit-reply-loss scenario by stopping `sshd`, exporting against its last authenticated receipt, deleting the full receiver directory, restoring a fresh directory from the signed backup and pinned checkpoint, then restarting real `sshd` to retrieve the original latest signed acknowledgment. It is a disposable single-runner recovery drill, **not a multi-host or production disaster recovery demonstration**.
