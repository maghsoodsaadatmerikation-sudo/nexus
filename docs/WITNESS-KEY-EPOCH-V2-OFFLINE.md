# v1-to-v2 witness acknowledgment key epochs: offline verifier only

## What changes

The independent witness custodian v1 pins one recipient Ed25519 signing key for every acknowledgment in its historical ledger. Simply replacing that key would make old signatures unverifiable. Existing three-party transition approvals are **consent evidence**, not an active migration or runtime authority.

This stage introduces a read-only **v2 candidate bridge verifier**:
\`scripts/workspace-witness-key-epoch-v2.py\`.

It accepts an intact v1 ledger, its independently retained signed last receipt/acknowledgment, a previously verified three-party approval document, and a proposed v2 continuation signed under the **new** recipient Ed25519 key. All are cross-bound to exact SHA-256 pins supplied by the operator. The historical v1 acknowledgment signatures stay unchanged and continue to verify with the outgoing key.

The verifier does not read production storage, create keys, create/sign real v2 acknowledgments, modify a custodian ledger, enable incoming-key acceptance, configure a server, switch a network listener, grant import permission or establish independent custody. The v1 recipient remains unchanged, and still refuses incoming-key signatures. CI fabricates only disposable receipts and keys.

## Proposed bridge schema

Strict JSON with these fields only:

\`\`\`json
{
  "schema": "nexus.offsite.receiver-key-epoch-bridge.v2",
  "old_ledger_sha256": "64 lowercase hex",
  "consent_sha256": "64 lowercase hex",
  "transition_proposal_sha256": "64 lowercase hex",
  "entries": [
    {"receipt": "v1 signed source receipt object", "ack": "v2 signed recipient acknowledgment object"}
  ]
}
\`\`\`

The JSON illustration uses strings for explanatory placeholders only; actual \`receipt\` and \`ack\` values are JSON objects.

Each \`ack\` is bound to \`schema=nexus.offsite.custodian-ack.v2\`, \`algorithm=Ed25519\`, \`epoch=2\` (integer), exact receiver/source/incoming signer identities, the full v1 source receipt hash and its state hash, exact monotonically incremented sequence, SHA-256 of the **full prior signed acknowledgment** and SHA-256 of the three-party-approved transition proposal. The first v2 acknowledgment's \`previous_ack_sha256\` must equal the last v1 signed acknowledgment digest; later v2 acknowledgments bind their immediate predecessor. V2 signatures use the separate domain \`NEXUS\0offsite-custodian-receipt-ack\0Ed25519\0v2\0\` with an 8-byte big-endian length prefix over canonical newline-terminated sorted JSON acknowledgment fields, preventing v1/v2 signature interchange.

The verifier revalidates **all** v1 history and each new v2 source receipt and recipient signature. Already acknowledged source receipts or state hashes cannot be repeated across the epoch boundary. It rejects an empty v2 continuation, wrong epoch/role, a branch, wrong historical checkpoint, stale independent sequence minimum, signature manipulation, extra/ambiguous JSON fields, reused signer keys, symlinks and hardlinks. Bridge size is bounded to 512 KiB and at most 64 v2 entries; these are verifier limits, not a production retention design.

## Required separately pinned material

Prepare and approve all exact SHA-256 file hashes separately from files, with independent authorization:

- \`--old-ledger\` and \`--old-ledger-sha256\` — a cold, complete v1 \`custodian.json\` with one or more signed entries
- \`--trusted-old-package\` and \`--trusted-old-package-sha256\` — exact last signed v1 receipt/ack package from independent custody
- \`--consent\` and \`--consent-sha256\` — 3-of-3 source/outgoing/incoming approved transition consent from the existing role-separated CLI
- \`--bridge\` and \`--bridge-sha256\` — candidate v2 bridge file
- \`--trusted-new-package\` and \`--trusted-new-package-sha256\` — separately retained last signed v2 receipt/ack package
- Operator-approved \`--receiver-id\`, \`--source-key-id\`, \`--outgoing-ack-key-id\`, \`--incoming-ack-key-id\`, and independently trusted public PEM files for all three signers
- \`--minimum-sequence\` — externally retained positive sequence floor, at least the length of the v1 ledger

If the operator does not possess all these independently retained inputs, the verifier must not be treated as proof of deployment readiness.

## Offline verification example

\`\`\`sh
python3 scripts/workspace-witness-key-epoch-v2.py \
  --old-ledger /independent/old-custodian.json \
  --old-ledger-sha256 APPROVED_OLD_LEDGER_SHA256 \
  --trusted-old-package /independent/old-latest-package.json \
  --trusted-old-package-sha256 APPROVED_OLD_PACKAGE_SHA256 \
  --consent /approvals/all-three-approved.json \
  --consent-sha256 APPROVED_CONSENT_SHA256 \
  --bridge /candidate/v2-bridge.json \
  --bridge-sha256 APPROVED_BRIDGE_SHA256 \
  --trusted-new-package /independent/latest-v2-package.json \
  --trusted-new-package-sha256 APPROVED_NEW_PACKAGE_SHA256 \
  --receiver-id independent-recipient \
  --source-key-id source-witness \
  --source-public-key /trusted/source.pub.pem \
  --outgoing-ack-key-id old-recipient \
  --outgoing-ack-public-key /trusted/old-recipient.pub.pem \
  --incoming-ack-key-id new-recipient \
  --incoming-ack-public-key /trusted/new-recipient.pub.pem \
  --minimum-sequence 42
\`\`\`

On success the command prints a JSON \`verified-offline-key-epoch-bridge\` report with old/new sequence, old/new end hashes and explicit \`production_cutover_authorized=false\`. On failure it exits nonzero. It does not write to or replace either v1 or v2 ledger. Temporary scratch space is used for public-key signature verification.

Run the adversarial synthetic regression:

\`\`\`sh
python3 scripts/test-workspace-witness-key-epoch-v2.py
\`\`\`

## Nonclaims and next engineering gate

This is a **proof of candidate cryptographic continuity**, not a full production migration. It does not ensure different organizations hold independent checkpoints or prevent two separately valid but dishonest histories from being signed by a compromised key. The verifier cannot resolve an authorization dispute after actual key compromise; it requires out-of-band recovery and revocation policy.

A future separately reviewed production-compatible v2 recipient must preserve the v1 ledger byte-for-byte; durably perform exactly-once epoch activation; use exclusive cross-process storage locks, backups and restore tests; handle signer crash and replay; keep old signer **verification-only** after cutover; and verify rollback and current-key trust using off-host checkpoints. A real production freeze and independent off-host restore evidence must precede activation. No such production cutover is implemented or authorized here.
