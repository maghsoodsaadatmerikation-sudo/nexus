# V2 witness durable candidate staging (OFFLINE, not production)

## Goal and dependency

The v1-to-v2 witness key-epoch verification in PR #226 proves a proposed sequence preserves all prior v1 signatures and uses the approved incoming recipient Ed25519 public key for v2 acknowledgments. It **does not** activate a new signing key on the live v1 receiver.

This step adds \`scripts/workspace-witness-v2-stager.py\`: an isolated **candidate-only storage layer** that durably stages a verified v2 bridge and exactly one externally signed acknowledgment per subsequent operation. The command does not produce or hold private signing keys, transport receipts to hosts, change any v1 ledger, import NEXUS data or deploy a production receiver.

The old v1 ledger, all independently approved signer identities, 3-of-3 transition consent, and independently retained latest v1 package are required as inputs for every staging operation. A proposed v2 bridge and its latest signed package must also be independently SHA-256 pinned. The tool delegates full signature validation to \`workspace-witness-key-epoch-v2.py\`, which checks all v1/v2 receipts and signed acknowledgments.

## Operator workflow

Prepare an isolated empty private location **outside a production volume** and prepare the exact signed v2 bridge, canonical JSON encoded via the existing strict NEXUS codec, plus a separately retained current v2 signed package.

Initialize a staging store (only a path that does not already exist):

\`\`\`sh
python3 scripts/workspace-witness-v2-stager.py init \
  --store /offline/new-v2-staging \
  --old-ledger /trusted/old-ledger.json \
  --old-ledger-sha256 PIN_OLD_LEDGER_SHA256 \
  --trusted-old-package /trusted/old-latest.json \
  --trusted-old-package-sha256 PIN_OLD_LAST_PACKAGE_SHA256 \
  --consent /approved/three-signatures.json \
  --consent-sha256 PIN_CONSENT_SHA256 \
  --receiver-id independent-recipient \
  --source-key-id approved-source \
  --source-public-key /trusted/source.pub.pem \
  --outgoing-ack-key-id old-ack \
  --outgoing-ack-public-key /trusted/old-ack.pub.pem \
  --incoming-ack-key-id new-ack \
  --incoming-ack-public-key /trusted/new-ack.pub.pem \
  --candidate /transport/candidate-v2.json \
  --candidate-sha256 PIN_CANDIDATE_SHA256 \
  --trusted-next-package /independent/last-v2-package.json \
  --trusted-next-package-sha256 PIN_LAST_V2_PACKAGE_SHA256 \
  --next-minimum-sequence 42
\`\`\`

To append a new externally signed entry, provide an entire **one-entry-longer canonical v2 bridge**, exact independently pinned SHA-256 of the **currently stored** candidate, and independently retained current and proposed next signed packages:

\`\`\`sh
python3 scripts/workspace-witness-v2-stager.py append \
  --store /offline/new-v2-staging \
  --old-ledger /trusted/old-ledger.json \
  --old-ledger-sha256 PIN_OLD_LEDGER_SHA256 \
  --trusted-old-package /trusted/old-latest.json \
  --trusted-old-package-sha256 PIN_OLD_LAST_PACKAGE_SHA256 \
  --consent /approved/three-signatures.json \
  --consent-sha256 PIN_CONSENT_SHA256 \
  --receiver-id independent-recipient \
  --source-key-id approved-source \
  --source-public-key /trusted/source.pub.pem \
  --outgoing-ack-key-id old-ack \
  --outgoing-ack-public-key /trusted/old-ack.pub.pem \
  --incoming-ack-key-id new-ack \
  --incoming-ack-public-key /trusted/new-ack.pub.pem \
  --candidate /transport/next-v2-candidate.json \
  --candidate-sha256 PIN_NEXT_CANDIDATE_SHA256 \
  --expected-current-sha256 PIN_CURRENT_CANDIDATE_SHA256 \
  --trusted-current-package /independent/current-v2-package.json \
  --trusted-current-package-sha256 PIN_CURRENT_V2_PACKAGE_SHA256 \
  --trusted-next-package /independent/next-v2-package.json \
  --trusted-next-package-sha256 PIN_NEXT_V2_PACKAGE_SHA256 \
  --current-minimum-sequence 42 \
  --next-minimum-sequence 43
\`\`\`

All paths and signer IDs must refer to independently checked values. The tool prints only a small JSON status, exact candidate SHA-256 and sequence. It never outputs a private key. SHA-256 pins should be retained in a different custody domain; computing a hash from the received candidate and immediately trusting it is **not independent attestation**.

## Crash consistency and idempotency model

- Staging directory is explicitly created with mode 0700 and cannot be re-initialized. It is locked with POSIX \`flock\` on its directory descriptor for cooperating appends.
- Every \`candidate.json\` is a single canonical, strict JSON file, regular, operator-owned, mode 0600, with link-count 1 and a 512 KiB cap. Unsafe or damaged input is rejected; no automatic reset or repair overwrites a previous state.
- A new candidate must have exactly one more entry, with **all** prior signed records byte-equivalent under the canonical encoding and all baseline commitments unchanged.
- Before overwrite, both old and new full ledgers and their independently pinned signed end packages are cryptographically rechecked. A second predecessor SHA-256 check occurs inside the locked directory.
- File is written to a random exclusive temporary file in the **same** filesystem, fsynced, renamed with \`os.replace\`, then parent directory fsynced. This is single-file atomic replacement on supporting local filesystems; it is not a distributed transaction or WORM proof.
- If a client retries the **identical** candidate after a response was lost, a reconstructed exact predecessor hash and both independently pinned signed packages must verify; the tool reports \`already-committed-exact-retry\` without creating an additional record.
- If a process exits before rename, the previous candidate remains valid; a leftover isolated temporary file is not treated as authoritative. If a process exits after rename but before directory fsync, the file must be checked after restart and may be either previous or next depending on storage guarantees; clients must re-read and verify before retrying.
- Different concurrent proposed continuations of the same predecessor are refused after the first valid commit. Distinct system users, hostile same-UID writers, remote shared storage and adversarial kernel/filesystem failures are **not** solved by cooperative directory locks.

## Explicit limitations

This is deliberately **not** a v2 production receiver, a network service, or a live key migration. It stages **externally prepared, already signed** candidate records; it does not issue signatures, autonomously accept arbitrary receipts, configure SSH or activate private keys. An independent custodian or source of trusted latest checkpoints has not been recruited. This process cannot prove that the trusted checkpoint was actually retained off host.

CI runs \`python3 scripts/test-workspace-witness-v2-stager.py\` using synthetic ephemeral Ed25519 signers. It checks exactly-once retries, two competing processes, actual abnormal exits on the atomic-rename boundary, manipulated signatures, damaged persisted files and untrusted link/permission states. All tests are fake and isolated.

Required future work before any real operation: independent custody, real encrypted off-host restore and witness confirmation, controlled production freeze and strict release gating, reviewed v2 online writer/receiver and durable epoch activation, recovery after signer compromise, real storage and host-level tests. No key cutover, user-data import or real deployment is authorized by this stage.
