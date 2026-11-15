# Independent NEXUS witness custodian: receipt ingestion and signed acknowledgments

## Scope and separation

This stage introduces a **standalone receiver-side CLI**, `scripts/workspace-witness-custodian.py`. It runs *outside* the NEXUS runtime and consumes only the small, signed external-state receipts from [OFFSITE-TRUST-ROLLBACK-WITNESS.md](OFFSITE-TRUST-ROLLBACK-WITNESS.md).

The receiver provides `init`, `receive`, `latest`, and `verify-package`. It never reads NEXUS conversations, workspace snapshots, API tokens, source private signing keys, or NEXUS runtime data. It does not open a port, host a website, deploy a service, connect cloud storage, issue runtime authority, or make its filesystem immutable.

To achieve **actual independent custody**, the receiver must be executed by a different organization/account on a separate controlled device or service and receive receipt files over an authenticated channel chosen by operators. **Two directories inside one test container or user account do not provide independent trust.** No such deployment or transport connection was performed in this change.

## Receiver setup and public-key enrollment

The NEXUS operator separately creates a state witness with `workspace-offsite-witness.py seal`. A distinct custodian independently pins:

- `source-key-id` and `source-public-key`: the offsite witness signer identity and public key, independently verified with the source operator
- `ack-key-id` and `ack-public-key`: the receiver's separate Ed25519 acknowledgment signer
- `receiver-id`: a pre-agreed receiver identity bound to all acknowledgments

Both public keys must differ. Neither private key belongs in the receiver's `custodian.json` ledger. Generate the receiver acknowledgment private key through a secure independent key custody mechanism; do not commit it to the repository or give it to NEXUS.

Example (all paths are illustrative; **do not run these commands against a shared production directory without a custodian and retention policy**):

```sh
# On the separate custodian machine, after independently approving public keys:
python3 scripts/workspace-witness-custodian.py init \
  --store /private/nexus-custodian \
  --receiver-id independent-organization-1 \
  --source-key-id rollback-2026-a \
  --source-public-key /trusted/rollback-signer.pub.pem \
  --ack-key-id custodian-2026-a \
  --ack-public-key /trusted/custodian.pub.pem

# Transport only the already signed receipt, not a workspace or secret.
python3 scripts/workspace-witness-custodian.py receive \
  --store /private/nexus-custodian \
  --receipt /inbox/checkpoint-000042.json \
  --ack-private-key /separately-protected/custodian.private.pem \
  > /outbox/acknowledged-000042.json

# Export the latest acknowledged receipt and signed acknowledgement.
python3 scripts/workspace-witness-custodian.py latest \
  --store /private/nexus-custodian \
  > /outbox/latest.json
```

The generated JSON package carries the original signed source receipt and a separately signed custodian acknowledgment. The latter binds:

- `receiver_id` and `sequence`, a **receiver-assigned monotonic number** starting at 1
- `source_receipt_sha256` and `state_sha256`
- Both signer key IDs
- `previous_ack_sha256` chaining the complete previous signed acknowledgment to the next

The receiver checks the entire existing chain under a POSIX locked directory, verifies every stored signature using **pinned public keys**, rejects duplicate source receipts or previously received state digests, and writes its bounded ledger with fsynced atomic replacement. A second process cannot admit the same receipt concurrently. Uninitialized, missing, corrupt, insecurely linked or weakly permissioned state fails closed. Its capacity is bounded at 256 acknowledgments and 2 MiB.

**The receiver's ledger is not WORM or tamper-proof against its own system administrator.** Signatures allow independent verification and make undetected edits difficult *without key compromise*, but a sufficiently privileged attacker can restore the full receiver directory or delete newer records. Preserve and pin periodically retrieved signed acknowledgments under a **second independent retention domain** if your threat model includes the receiver being compromised.

## Authenticated SSH handoff and exact-receipt retry

A separately operated SSH forced-command adapter and pinned SSH client are
now available in [PINNED-SSH-WITNESS-HANDOFF.md](PINNED-SSH-WITNESS-HANDOFF.md).
The receiver accepts a **bounded, authenticated stdin receipt** and the
client verifies both Ed25519 signatures before saving the acknowledgment.
A lost reply after a committed write can be recovered by resending the
**exact latest signed receipt** without advancing the receiver's sequence.

No external host, SSH account, pinned production host key or genuine
independent receipt delivery is provisioned by the repository.

## Independent verification from the NEXUS side

The user/operator must **obtain the package from the independently authenticated custodian**, not from a mutable local NEXUS folder, and independently select the custodian's public key and the source witness public key. A local sequence floor anchored outside NEXUS detects a subsequently supplied stale package.

```sh
python3 scripts/workspace-witness-custodian.py verify-package \
  --package /inbox/latest-from-custodian.json \
  --expected-receiver-id independent-organization-1 \
  --trusted-source-key-id rollback-2026-a \
  --trusted-source-public-key /trusted/rollback-signer.pub.pem \
  --trusted-ack-key-id custodian-2026-a \
  --trusted-ack-public-key /trusted/custodian.pub.pem \
  --minimum-sequence 42 \
  --state-dir /private/nexus-operator-trust
```

The optional `--state-dir` compares the **current validated local NEXUS trust-state commitment** with the source receipt's size, SHA-256 and key/workspace counts. Any legitimate local update after the custodian last acknowledged a receipt is a mismatch until a new receipt is transferred and acknowledged. Do not silently downgrade `--minimum-sequence` when a stale reply is received. `verify-package` checks the cryptographic authenticity of the two signatures, one receiver-assigned sequence and (optionally) local state equality; it **cannot independently discover the globally latest sequence** unless the external receiver communication and client pinning are trustworthy.

If a custodian's signing key is compromised, its operator must perform a reviewed out-of-band key rotation/recovery protocol; this v1 ledger deliberately refuses to silently change pinned keys. Restoring a deleted ledger is also an operator incident, not a reason to initialize a replacement and call it continuous history.

## Privacy, operational limits and next security step

- **Never send private signing keys, raw workspaces, user conversations or authentication headers to the custodian.** Receipt state hashes still disclose aggregate metadata and may allow correlation; handle them as controlled operational records.
- The receiver's command-line output is designed for file transfer over *separately managed* authenticated channels. It does not provide TLS/mTLS or network transport and should not be exposed via an unauthenticated HTTP service.
- The receiver signs **receipt acceptance**, not the truth of the original analysis, a trusted timestamp, an unchangeable publication, an actual human decision, or a right to NEXUS import. Existing `POST /v1/workspaces/import` machine-history denial remains unchanged.
- Source receipts v1 do not attest a total ordering of NEXUS state revisions. The receiver prevents repeats of previously accepted states and chains its own *acceptance order*, but may accept a previously unseen yet old source-signed receipt. Real freshness still requires an authenticated independent checkpoint service and source-side revision promises.
- No actual offsite organization, separate OS account, storage bucket, remote service, backup or domain was created by this change. Completion of **operational** anti-rollback will require a selected external custodian/provider, securely pinned identities, an authenticated transport, independent durable retention and incident drills.

## Synthetic regression

Run `python3 scripts/test-workspace-witness-custodian.py` to generate separate disposable real Ed25519 keypairs and simulate transfer between an operator and a receiver. Tests cover acceptance, signed receipt chain and latest retrieval, source/receiver spoofing, wrong keys, stale sequence floors, local state rollback, repeated receipts under different nonces, malicious metadata, duplicate JSON keys, receiver-ledger corruption/permission/link attacks and simultaneous submissions. These tests are also part of the read-only PR verification gate.

The test's two local directories are **not** evidence of actual independent custody or deployment.
