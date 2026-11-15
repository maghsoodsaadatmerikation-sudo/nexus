# Receiver signing-key transition: three-party offline consent (not cutover)

## Why this exists

The NEXUS witness custodian v1 signs every receipt using a single Ed25519
recipient private key bound to the public key in its validated ledger. Its
previous acknowledgments cannot be verified with an unrelated replacement
key. Silently swapping the private key or overwriting the ledger would
break historical verification and could reset the independent sequence.

This stage provides an **offline, cryptographically verified consent
ceremony** that freezes the exact last independently retained acknowledgment
and requires **three independent role signatures**:

1. **Source**: the NEXUS state-witness signer approves the receiver identity,
   latest signed package and new recipient key.
2. **Outgoing recipient**: the currently authorized signing key approves the
   same exact transition proposal.
3. **Incoming recipient**: the proposed replacement signing key proves
   possession and approves the same proposal.

**Important:** Three signed consents are *not* an active key rotation or an
authorization to accept new receipts. They can be used as prerequisites for
a separately reviewed, versioned ledger migration. The current v1 receiver
remains pinned to the outgoing key, with its former receipt and acknowledgment
history intact. This command will never mutate the receiver state, activate
or generate any key, change SSH host identities or grant NEXUS import
authority. A compromised outgoing key cannot be repaired purely by obtaining
its own signature; handle loss/compromise under an independent incident
procedure with additional trust/revocation approvals.

## Files and explicit trusted inputs

`scripts/workspace-witness-key-transition.py` implements three local commands:

- `prepare`: independently verify the prior signed latest package, its
  **operator-pinned exact SHA-256 digest**, receiver identity, source and
  current recipient public keys, and an **exact latest sequence**. Bind all
  that into a deterministic, strict JSON proposal that also specifies the
  proposed new recipient key ID and DER fingerprint.
- `sign`: one role at a time, using only **that role's private key** and a
  separately preapproved SHA-256 of the exact proposal. The role's private
  key must match the role's public-key commitment. The old document is
  never overwritten. Signatures use a role-separated Ed25519 domain.
- `verify`: require all three correctly typed signatures, verify them
  against **separately supplied trusted public keys**, check the exact
  externally pinned latest package and full source/ack signatures, verify
  role IDs and fingerprints, and reject a changed or stale sequence.

The proposal embeds fingerprints and hashes, not private keys, workspace
snapshots, conversations or API credentials.

## Illustrative workflow

Every custodian verifies proposed changes and signer identities **out of
band** before signing. The exact package digest and sequence must be held
outside the receiver's mutable registry. The three signatures should be
created in separate key custody domains, never by copying all private keys
onto a NEXUS host or GitHub Actions runner. CI only uses disposable keys.

Prepare a proposal from a previously independently retained signed package:

```sh
python3 scripts/workspace-witness-key-transition.py prepare \
  --receiver-id independent-recipient \
  --source-key-id source-witness \
  --source-public-key /trusted/source.pub.pem \
  --outgoing-ack-key-id recipient-old \
  --outgoing-ack-public-key /trusted/old-recipient.pub.pem \
  --incoming-ack-key-id recipient-new \
  --incoming-ack-public-key /trusted/new-recipient.pub.pem \
  --trusted-latest-package /retained/latest-signed.json \
  --trusted-package-sha256 APPROVED_EXACT_SIGNED_PACKAGE_SHA256 \
  --minimum-sequence 42 \
  --output /consent/proposal.json
```

Approve and securely communicate the printed `proposal_sha256` *through an
independent process*, not merely from the same unverified file. Source,
outgoing and incoming custodians **each** independently review the proposal
and sign using their own private key; signatures are collected in a sequence
of files with identical proposal content:

```sh
python3 scripts/workspace-witness-key-transition.py sign \
  --role source \
  --private-key /source-custody/source-private.pem \
  --trusted-proposal-sha256 APPROVED_PROPOSAL_SHA256 \
  --input /consent/proposal.json \
  --output /consent/source-approved.json

# Separately, in the outgoing recipient's private key custody:
python3 scripts/workspace-witness-key-transition.py sign \
  --role outgoing \
  --private-key /outgoing-custody/old-private.pem \
  --trusted-proposal-sha256 APPROVED_PROPOSAL_SHA256 \
  --input /consent/source-approved.json \
  --output /consent/outgoing-approved.json

# Separately, in the incoming recipient's private key custody:
python3 scripts/workspace-witness-key-transition.py sign \
  --role incoming \
  --private-key /incoming-custody/new-private.pem \
  --trusted-proposal-sha256 APPROVED_PROPOSAL_SHA256 \
  --input /consent/outgoing-approved.json \
  --output /consent/all-three-approved.json
```

Verify the complete approval from separately pinned public keys and
latest receipt:

```sh
python3 scripts/workspace-witness-key-transition.py verify \
  --receiver-id independent-recipient \
  --source-key-id source-witness \
  --source-public-key /trusted/source.pub.pem \
  --outgoing-ack-key-id recipient-old \
  --outgoing-ack-public-key /trusted/old-recipient.pub.pem \
  --incoming-ack-key-id recipient-new \
  --incoming-ack-public-key /trusted/new-recipient.pub.pem \
  --trusted-latest-package /retained/latest-signed.json \
  --trusted-package-sha256 APPROVED_EXACT_SIGNED_PACKAGE_SHA256 \
  --minimum-sequence 42 \
  --input /consent/all-three-approved.json
```

The verifier deliberately prints `no actual key rotation or import
authority` on success. Do not point `workspace-witness-host.py` at the new
private key while the v1 ledger pins the outgoing key. Its preflight must
continue to reject a new unapproved signer.

## Threat model and limitations

- **No role may approve itself as a different role** by reusing a public
  key or key ID. A different incoming key can be approved only if all three
  independent domains agree on the same proposal and last signed checkpoint.
- A proposed cutover tied to old sequence 42 must fail verification when
  the independently retained minimum accepted sequence advances to 43.
  Do not claim that checking sequence against a mutable local file proves
  it is the globally latest.
- Approvals do not by themselves prove the custodians are organizationally
  separate. **Key custody and external storage separation remain manual,
  audited operational requirements.** A malicious single administrator
  controlling all three keys can sign any proposal.
- None of these commands opens or changes an SSH service, edits a NEXUS
  workspace, updates a receiver ledger or creates a replacement key. Do
  not infer downtime, readiness, safety after private-key compromise,
  active revocation or production deployment from a passed consent check.
- The next engineering phase needs a separate, backward-compatible ledger
  key epoch scheme preserving old signatures while verifying new ones,
  together with a verified and rollback-resistant cutover. Until that is
  implemented, this is a strictly bounded **prepare-and-consent** stage.

## Regression evidence

`scripts/test-workspace-witness-key-transition.py` generates disposable
source/outgoing/incoming Ed25519 keypairs in separate test folders, enrolls
and obtains a real source/recipient-signed checkpoint and then checks:

- Exact package and proposal SHA-256 commitments
- All three independent roles, distinct signer IDs, wrong private keys,
  duplicate approvals and incomplete consent
- Forged receiver/role IDs, altered fingerprints, swapped signature roles,
  edited sequence, unknown JSON fields and duplicate JSON keys
- Old/stale external sequence floors and revoked data-key continuation
- An important **nonactivation guarantee**: v1 receiver still rejects
  the new recipient private key even with a fully valid transition consent

The normal read-only GitHub PR test suite includes this regression. The
three party folders are synthetic; no external provider or live key custody
was established.
