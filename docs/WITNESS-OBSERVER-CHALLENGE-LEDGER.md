# Operator-owned one-time challenge ledger for two signed witness observations

## Scope and threat model

\`scripts/workspace-witness-challenge-ledger.py\` provides **offline, POSIX-only, locally durable** issuance and one-time consumption of 256-bit cryptographically random challenges. It is a separate operator-owned/private ledger for the two observer reports created in PR #229. This is **not** a network service, physical-host independence proof, public identity authority, remote clock, online replay-resistant protocol, or release permission.

A mere \`verify-pair\` of two valid signed reports is still replayable in isolation. For a workflow needing **one-time** acceptance, use this challenge ledger's \`consume\` mode **instead of treating \`verify-pair\` as an acceptance decision**. \`consume\` revalidates the entire signed v1/v2 history, exact three-party signer transition, independent latest signed checkpoint/sequence floor, each separately pinned observer signature and their common challenge, then atomically marks that challenge consumed. A second successful consume of the same challenge is refused, including after program restart and on two concurrent cooperating processes.

## Durable event format

A new private directory contains exactly one authoritative \`challenges.json\`, mode 0600. The strict canonical JSON schema is \`nexus.offsite.observer-challenge-ledger.v1\` with \`events\` array bounded at 256 events and 128 KiB. Every event has a **monotonic integer sequence** and \`previous_event_sha256\`, equal to the canonical SHA-256 of the previous event (genesis is all zeros). No event can be removed, reordered, rewritten, or duplicated **without breaking a separately retained complete-registry SHA-256 pin**; the in-file hashes alone are not an independently protected signature or true WORM record.

- \`issue\` events commit a freshly generated \`secrets.token_hex(32)\` 256-bit challenge; a challenge cannot be issued twice in the same ledger.
- \`consume\` events bind the issuance to independently pinned origin/recovery observer report hashes, the fully verified v2 bridge hash and its last signed acknowledgment and sequence. A challenge can be consumed once only. Report signer keys must be distinct from each other and from the source/receiver keys.
- All state transitions require the operator's **independently retained exact predecessor \`--expected-registry-sha256\`**. The app holds an exclusive \`flock\` on the private directory through verification and commit, writes an exclusive temporary file with \`fsync\`, atomically replaces the single registry file, \`fsync\`s the parent directory, and rereads the newly written state. Restarts must compare the current register against the independently retained hash before continuing.

## Procedure

1. In a physically distinct, trusted review custody domain (when available), select an absolute new directory under an operator-owned private parent and run:
   \`\`\`sh
   python3 scripts/workspace-witness-challenge-ledger.py init \
     --registry /private-review/challenge-ledger
   \`\`\`
   Retain the returned \`registry_sha256\` in a **separate** trust/failure domain. The command creates a fresh mode-0700 directory only and never overwrites an earlier ledger.
2. To issue a new challenge, run:
   \`\`\`sh
   python3 scripts/workspace-witness-challenge-ledger.py issue \
     --registry /private-review/challenge-ledger \
     --expected-registry-sha256 PIN_PREVIOUS_REGISTRY_HEAD
   \`\`\`
   The result has \`challenge_hex\` and a **new** \`registry_sha256\`. Record this hash out of band *before* releasing the challenge to the origin/recovery observers. Do not let either observer choose their own verifier challenge.
3. On separate observer custody systems, run the existing \`scripts/workspace-witness-two-custody-evidence.py observe\` with the exact issued challenge. They must use separate private Ed25519 observer keys and independently verified signed v2 history. Copy the **signed** reports to review custody, separately pin their file hashes and trusted public keys.
4. Run \`consume\` with \`--registry\` and the last **independently retained** \`--expected-registry-sha256\`, plus all the shared \`verify-pair\` arguments (except the initial \`verify-pair\` word). The shared arguments are the independently pinned v1 ledger, v1 package, transition consent, source/outgoing/incoming signer identities and public keys, v2 latest signed package and its SHA-256, externally approved v2 bridge hash, known minimum sequence, exact issued challenge, approved full bridge path, and **both exact independently SHA-256-pinned signed observation reports with their corresponding observer keys/IDs**. For the full argument list, see \`WITNESS-TWO-CUSTODY-EVIDENCE.md\`.
   \`\`\`sh
   python3 scripts/workspace-witness-challenge-ledger.py consume \
     --registry /private-review/challenge-ledger \
     --expected-registry-sha256 PIN_REGISTRY_AFTER_ISSUE \
     [SAME_VERIFY_PAIR_ARGUMENTS_EXCEPT_COMMAND]
   \`\`\`
   Treat the bracketed placeholder as documentation, not a literal CLI argument. The tool will refuse a challenge that was never issued or that is already consumed. On success, it emits the new registry head digest and a report with **\`production_release_authorized=false\`**.
5. To inspect a pinned registry after a lost response or process restart, run:
   \`\`\`sh
   python3 scripts/workspace-witness-challenge-ledger.py inspect \
     --registry /private-review/challenge-ledger \
     --expected-registry-sha256 PIN_INDEPENDENT_HEAD
   \`\`\`
   The response lists pending challenge values, consumed count and exact registry hash. This is read-only and does not grant another successful consume. If the hash differs from the separately saved head, investigate tampering or crash recovery **before** issuing or consuming anything else.

## Constraints and security boundaries

- The tool prevents replay **within the currently pinned ledger history**. A compromised reviewer who can replace both the file and all out-of-band pins can bypass these checks. A hash-linked event log alone does not prove WORM, geographic separation, independently controlled custody, tamper-proof hardware or globally unique challenge use across another registry.
- An unexpected process exit before atomic replacement leaves the previous file authoritative; one after replacement but before the directory \`fsync\` may leave either version after a real power loss. **Read and compare the current exact SHA-256 with the independently retained checkpoint** and resolve any discrepancy with independent custody evidence before further steps.
- A lost \`issue\` response can be inspected with a trusted current head. A lost \`consume\` response never warrants blindly resubmitting; inspect the pinned ledger and verify that the signed observation hashes and challenge are recorded.
- 256 events is a deliberate limit. Exhaustion fails closed; there is no silent pruning, truncation or implicit registry reinitialization. Planned retirement requires a separately authorized and externally checked transition to a new ledger; this release does not provide one.
- CI uses ephemeral synthetic keys and local private folders, not separate physical computers. It cannot prove network identity, actual independent custody, real power-loss durability, offsite restore, or compliance with any production release gate.

To run the adversarial fixture:
\`\`\`sh
python3 scripts/test-workspace-witness-v2-stager.py
\`\`\`

Do not merge or deploy before actual independent-host evidence, trusted external checkpoint custody and reviewed operational recovery procedures exist.
