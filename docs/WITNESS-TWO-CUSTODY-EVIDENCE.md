# NEXUS two-custody observation evidence: offline operator protocol

## Purpose and limits

This stage enables **two distinct human or organizational custodians to independently sign their observation of the same restored NEXUS v2 witness history**. It is an offline, challenge-bound evidence protocol, not a network-based independent-host test or permission to deploy a production service.

Tool: \`scripts/workspace-witness-two-custody-evidence.py\`, commands \`observe\` and \`verify-pair\`.

\`observe\` takes a locally accessible and **private** staged-v2 candidate directory, rechecks every old-v1 and new-v2 Ed25519 signature against independently pinned identities, checks exactly the most recent independently signed v2 package and a separate monotonic sequence floor, and signs an observation with a *separately provisioned* Ed25519 observer private key. It does not write or alter the staging store. \`verify-pair\` independently validates the signed v2 full chain and checks two role-separated observer signatures against separately pinned public keys and reports.

**Important:** Two distinct public keys, two claims of observer identity, or two directory paths **do not prove two physically independent hosts**. The cryptographic result must always emit \`physical_host_independence_proven=false\`, \`real_offsite_restore_performed=false\`, and \`production_release_authorized=false\`. Real physical independence must be checked with host/operator infrastructure evidence *outside* this file-based cryptographic protocol. A single party with two private keys can fabricate both signed observations.

## Independent inputs

Before any real two-host drill, the operator must obtain independently and record:

- Exact SHA-256 fingerprints of the complete legacy v1 ledger and the last signed v1 receipt-plus-acknowledgment package.
- All three independently validated role-separated Ed25519 signer IDs and public PEM keys (source, outgoing v1 receiver, incoming v2 receiver), together with separately retained 3-of-3 key-transition consent and its SHA-256.
- Independently approved SHA-256 of the complete v2 bridge, the latest signed v2 package and a monotonic, externally retained minimum sequence.
- A **new, unpredictable, 32-byte hex challenge** created in a separate custody domain, distributed securely to both operators *before* their observations. Track use outside the CLI; this tool cannot assert nonce uniqueness, freshness, accurate wall time or eliminate replay when an operator reuses a challenge.
- Distinct observer IDs and Ed25519 key pairs for each role. **Neither observer key may equal any source or receiver signer key**, nor may both observer roles use the same key. Private observer keys must remain in their original custody; never copy both to one system for a real drill.

\`--role origin\` is the initial custodian observation; \`--role recovery\` is the second custodian observation after independently recovering a staged v2 history from cold backup. The host identities and execution environments are **declared** rather than cryptographically proven.

## Workflow

1. Run the existing offline v2 \`export\`, \`verify\`, \`restore\` steps in separate controlled environments; record all independent hashes and the exact minimum sequence.
2. On the origin operator's machine, run \`observe\` with its private, fresh origin observer key. On the separate recovery operator's machine, repeat with \`--role recovery\` and that operator's **different** private key. Operators must not share private keys.
3. Deliver both signed canonical JSON reports to a separate reviewer, retaining their **exact file SHA-256 hashes** out of band.
4. Run \`verify-pair\` from a separate trusted review environment, providing the entire candidate bridge, both exact signed report hashes, both independently approved public keys and IDs, and the original historical-signature verification materials. The tool outputs only a proof of two distinct signer observations, never a claim of independent physical hosts.
5. Do not release or cut over production on the strength of this tool. A separately reviewed real-host drill, physical host evidence, encrypted off-host backup, failure-domain independence, live disaster simulation, key compromise procedure and explicit release approvals remain blockers.

Both CLI modes share the following arguments (supply exact independently pinned values):

\`\`\`sh
--old-ledger /trusted/old-v1-ledger.json
--old-ledger-sha256 PIN_OLD_LEDGER
--trusted-old-package /trusted/old-v1-package.json
--trusted-old-package-sha256 PIN_OLD_PACKAGE
--consent /trusted/three-party-consent.json
--consent-sha256 PIN_CONSENT
--receiver-id independent-recipient
--source-key-id source-signer
--source-public-key /trusted/source.pub.pem
--outgoing-ack-key-id old-receiver
--outgoing-ack-public-key /trusted/old-receiver.pub.pem
--incoming-ack-key-id new-receiver
--incoming-ack-public-key /trusted/new-receiver.pub.pem
--trusted-latest-package /trusted/latest-signed-v2-package.json
--trusted-latest-package-sha256 PIN_LATEST_PACKAGE
--expected-bridge-sha256 PIN_COMPLETE_V2_BRIDGE
--minimum-sequence 42
--challenge-hex 64_LOWERCASE_HEX_CHALLENGE
\`\`\`

Origin observer additional args:

\`\`\`sh
python3 scripts/workspace-witness-two-custody-evidence.py observe \
  [COMMON_ARGUMENTS] \
  --role origin \
  --store /offline/origin-candidate-directory \
  --observer-id origin-observer-key-01 \
  --observer-public-key /trusted/origin-observer.pub.pem \
  --observer-private-key /private/origin-observer.pem \
  --output /private/observations/origin-observation.json
\`\`\`

Recovery observer uses the same command and approved challenge with \`--role recovery\`, its own restored private stage path, **different** private/public signer keys, observer ID and output file.

Review:

\`\`\`sh
python3 scripts/workspace-witness-two-custody-evidence.py verify-pair \
  [COMMON_ARGUMENTS] \
  --approved-bridge /trusted/full-verified-v2-bridge.json \
  --origin-report /observations/origin-observation.json \
  --origin-report-sha256 PIN_ORIGIN_OBSERVATION \
  --origin-public-key /trusted/origin-observer.pub.pem \
  --origin-observer-id origin-observer-key-01 \
  --recovery-report /observations/recovery-observation.json \
  --recovery-report-sha256 PIN_RECOVERY_OBSERVATION \
  --recovery-public-key /trusted/recovery-observer.pub.pem \
  --recovery-observer-id recovery-observer-key-02
\`\`\`

The placeholders \`[COMMON_ARGUMENTS]\` must be replaced with the actual options above, not passed verbatim. A signature can attest to what an operator's key signed, but not to the operator's claimed physical location or to unobserved execution on another machine.

## Fail-closed tests

The \`scripts/test-workspace-witness-v2-stager.py\` regression includes a full synthetic Ed25519 v1→v2→cold-backup→fresh-restore→two-roles chain. It rejects reused signer keys, wrong role or signer identity, changed challenge, stale sequence, invalid independently pinned report hash, wrong latest package, changed signature/ack/hash, unknown report fields, JSON ambiguity, linked report files and a missing locally verified staging head.

CI is not a real remote receiver. It does not operate two separate physical machines or provide public HTTPS, independent endpoint continuity, backups on another host, real encrypted restore or a real production release decision. Even a green PR must remain in Draft until separate release gates are met.
