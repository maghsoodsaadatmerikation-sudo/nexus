# Offline v2 custodian cold backup and recovery drill

## Scope

This step adds **verification-only recovery tooling** for the separately staged, cryptographically signed v2 witness ledger. It builds on the v1 historical-prefix proof (#224), v2 three-party key-epoch proof (#226), and atomic off-service staging (#227). None of these features activates a new private signer, alters NEXUS production trust, or establishes a real independent recipient.

CLI: \`scripts/workspace-witness-v2-recovery.py\` with \`export\`, \`verify\`, and \`restore\`.

- \`export\` takes a locked, private v2 staging directory, revalidates the complete v1 history, transition consent, v2 Ed25519 chain, **externally pinned exact head SHA-256**, independent latest signed v2 checkpoint and sequence floor, then writes a new private canonical cold-backup file with \`O_EXCL\`, file \`fsync\`, and directory \`fsync\`. Existing backups cannot be overwritten.
- \`verify\` accepts a cold backup and **independently retained** backup file SHA-256, v2 head SHA-256, latest signed package SHA-256 and monotonic sequence minimum, and checks all of these against each other and the original source/outgoing/incoming signer identities. No backup content is trusted merely because it contains a hash.
- \`restore\` performs the same checks **before creating a destination**, writes a candidate file into a **fresh** operator-owned mode-0700 staging directory using the existing atomic stager, and **reads back and revalidates every signature**. Existing or damaged stores are never overwritten or repaired automatically.

The cold backup schema \`nexus.offsite.v2-candidate-backup.v1\` contains **only public signed history**, no private signing key, with exact fields \`schema\`, \`candidate\`, \`candidate_sha256\`, \`latest_ack_sha256\`, \`latest_sequence\`. It is bounded to the existing candidate size cap plus 16 KiB. The backup encoding must be canonical strict JSON, and all independently pinned digests are 64 lowercase hexadecimal characters.

## Independent custody is an operator responsibility

Run \`export\` on an *offline copy* of the trusted v2 staging material, not a production trust volume. Copy the cold backup to a separately governed storage/failure domain (preferably physically different), **and separately** retain its exact SHA-256, latest signed package and pinned minimum sequence in a trusted custody ledger. Do not calculate these pins from a potentially attacker-controlled backup during restore and call that independent verification. A legitimate but stale signed backup must be rejected when its sequence is below the independently approved floor. A valid signed fork with the same sequence must be rejected when its last package differs from the independent reference.

### Export example

\`\`\`sh
python3 scripts/workspace-witness-v2-recovery.py export \
  --store /offline/operator-v2-stage \
  --backup /private-cold-storage/custodian-v2-backup.json \
  --old-ledger /trusted/v1-ledger.json \
  --old-ledger-sha256 PIN_V1_LEDGER_SHA256 \
  --trusted-old-package /trusted/v1-latest.json \
  --trusted-old-package-sha256 PIN_V1_LATEST_SHA256 \
  --consent /trusted/three-parties.json \
  --consent-sha256 PIN_CONSENT_SHA256 \
  --receiver-id independent-recipient \
  --source-key-id source-witness \
  --source-public-key /trusted/source.pub.pem \
  --outgoing-ack-key-id old-signer \
  --outgoing-ack-public-key /trusted/old.pub.pem \
  --incoming-ack-key-id new-signer \
  --incoming-ack-public-key /trusted/new.pub.pem \
  --expected-bridge-sha256 PIN_CURRENT_V2_HEAD_SHA256 \
  --trusted-latest-package /independent/v2-latest.json \
  --trusted-latest-package-sha256 PIN_V2_LATEST_SHA256 \
  --minimum-sequence 42
\`\`\`

The resulting JSON report includes \`backup_sha256\`. Preserve that value independently, not only in the backup volume. Export requires the backup's **immediate parent directory** to be owner-private and the output file not to exist.

### Verify the cold copy

\`\`\`sh
python3 scripts/workspace-witness-v2-recovery.py verify \
  --backup /restored-cold-media/custodian-v2-backup.json \
  --backup-sha256 INDEPENDENT_BACKUP_SHA256 \
  --old-ledger /trusted/v1-ledger.json \
  --old-ledger-sha256 PIN_V1_LEDGER_SHA256 \
  --trusted-old-package /trusted/v1-latest.json \
  --trusted-old-package-sha256 PIN_V1_LATEST_SHA256 \
  --consent /trusted/three-parties.json \
  --consent-sha256 PIN_CONSENT_SHA256 \
  --receiver-id independent-recipient \
  --source-key-id source-witness \
  --source-public-key /trusted/source.pub.pem \
  --outgoing-ack-key-id old-signer \
  --outgoing-ack-public-key /trusted/old.pub.pem \
  --incoming-ack-key-id new-signer \
  --incoming-ack-public-key /trusted/new.pub.pem \
  --expected-bridge-sha256 INDEPENDENT_HEAD_SHA256 \
  --trusted-latest-package /independent/v2-latest.json \
  --trusted-latest-package-sha256 PIN_V2_LATEST_SHA256 \
  --minimum-sequence 42
\`\`\`

### Recover into a new private staging directory

Use the same arguments as \`verify\`, but replace \`verify\` with \`restore\` and append \`--new-store /private-recovery-parent/new-v2-staging\`. The new store **must not already exist**. It is not an authority-bearing live receiver. Re-check and retain the report's exact bridge hash and sequence after restore.

## Failure semantics

- A modified backup (even if attacker rehashes its file), bad v2 signature, missing three-party authorization, wrong head, replayed v1/v2 receipt, substituted public key, wrong signed end-package, and independently detected rollback are rejected.
- Symlink/hardlink backup files, ambiguous JSON, noncanonical JSON, overwrite attempts and shared output directories are rejected.
- If the process dies during creation, the fresh staging directory may exist without a completed candidate; the operator must investigate/discard this isolated **new** destination explicitly. The tool does not silently reinitialize it or overwrite an earlier valid store.
- The recovery CLI cannot prove the second storage medium is independent merely from different local paths. Synthetic CI uses temp files and disposable Ed25519 signers, **not** an offsite real-host restore, hardware failure or a forensic antirollback anchor.
- No encryption-at-rest is implemented by this step. Backups contain public signed metadata and may still expose sensitive structural information; secure storage and transport are required.

## Test and real-environment gates

Run \`python3 scripts/test-workspace-witness-v2-stager.py\` or the exact-head dedicated PR workflow. The end-to-end fixture covers real ephemeral Ed25519 key pairs, non-replay, competing branches, abnormal process exits, cold backup/restore, tampering, a valid-but-stale signed snapshot, links, and corrupt input.

Before enabling an actual v2 witness receiver: independently retained off-host history, tested encrypted restore on a separate real host, explicitly reviewed signer migration and revocation, incident response and production rollback gates, and release approval are still required. A successful test does not grant deployment, key-cutover or data-import authority.
