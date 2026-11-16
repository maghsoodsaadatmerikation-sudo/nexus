# Phase 32 — explicit trusted-head checkpoints for offline recovery

## Purpose and boundary

Phase 31 encrypts and authenticates a signed snapshot, but an authentic OLD
snapshot can still be replayed. Phase 32 adds a distinct Ed25519-signed
checkpoint envelope with a monotonically advancing sequence number and exact
previous-checkpoint SHA-256 linkage. The recovery operation MUST be given an
exact latest checkpoint SHA-256 AND sequence from an independently retained
trusted record; otherwise it rejects before creating plaintext data.

Critically, this tool does NOT discover, attest, store, or update the true
latest head in a separate system. A user who takes both the archive and the
latest SHA from the same untrusted source has NO anti-rollback protection.
A future independent nonrewindable custodian or separately held offline record
is a mandatory production security gate.

## Three offline operator commands

- publish: sign a new canonical checkpoint with an independent checkpoint
  Ed25519 key. Genesis must explicitly use predecessor SHA 64 zeroes and
  predecessor sequence 0, subject to an external human approval. A successor
  requires the exact approved predecessor SHA, previous checkpoint file,
  valid predecessor signature, matching workspace and signing key, and
  increments sequence by exactly one.
- check: require exact independently supplied latest-head SHA and sequence,
  trusted checkpoint signer raw Ed25519 public key SHA-256, and a valid
  checkpoint signature. Optionally compare the encrypted archive SHA-256
  and visible encrypted header against signed checkpoint metadata.
- recover: require explicit approval, independent latest head SHA and
  sequence, matching keys, AES-256-GCM ciphertext and detached snapshot
  Ed25519 signature, a private temporary scratch directory, and an empty
  private destination root. It verifies the checkpoint BEFORE decrypting,
  checks authenticated encryption, re-verifies complete snapshot contents
  and journal using Phase 30, then restores once without starting jobs.
  Plaintext ZIP is transiently stored on scratch and normally cleaned up.

Each signed checkpoint binds workspace identity, sequence, exact predecessor
SHA-256, original archive SHA-256, encrypted envelope SHA-256, workspace
manifest SHA-256, approved snapshot signer public-key fingerprint, and
approved independent checkpoint signer public-key fingerprint.

## Key and publication policy

Use a distinct Ed25519 checkpoint signing key rather than the existing
snapshot signer. Keep private PEM mode 0600, key folder mode 0700; never
upload signing keys or actual user backups to GitHub Actions. Verify the
raw public key fingerprint independently of the checkpoint host.

The operator MUST independently approve and retain the latest head SHA and
sequence after publishing every checkpoint. This CLI intentionally does
not mutate any local/global latest pointer. Without independently controlled
immutable storage and confirmation at recovery, old but valid checkpoints
can still be replayed by supplying old pins.

No automatic trusted time, remote witness, custodian enrollment, anti-fork
evidence, signer revocation, independent provider, production backup key
escrow or key rotation is claimed.

## Example commands

Set independently verified ARCHIVE_SHA, WORKSPACE_SHA, ENCRYPTED_SHA,
SNAPSHOT_SIGNER_SHA, CHECKPOINT_SIGNER_SHA and for recovery the independently
retained LATEST_SHA and LATEST_SEQ. All directories must be private 0700;
all files must be owner-owned and private. Nonroot Linux only.

Create the first checkpoint, only after explicit external approval to
initialize the chain:

~~~bash
python3 scripts/nexus-operator-checkpoint.py publish \
  --checkpoint /private/checkpoints/head-1.json \
  --checkpoint-public-key /private/keys/checkpoint-public.pem \
  --checkpoint-private-key /private/keys/checkpoint-private.pem \
  --checkpoint-signer-sha256 "$CHECKPOINT_SIGNER_SHA" \
  --workspace acceptance \
  --sealed /private/transfer/snapshot.sealed \
  --encrypted-sha256 "$ENCRYPTED_SHA" \
  --archive-sha256 "$ARCHIVE_SHA" \
  --workspace-sha256 "$WORKSPACE_SHA" \
  --snapshot-signer-sha256 "$SNAPSHOT_SIGNER_SHA" \
  --previous-sha256 "$(printf '%064d' 0)" \
  --previous-sequence 0 --approve-publish
~~~

Independently retain its returned checkpoint SHA and sequence. For a
successor, provide --previous-checkpoint with that file and exact independently
approved --previous-sha256 / --previous-sequence; do not trust an unreviewed
local pointer.

Check the exact independently approved head:

~~~bash
python3 scripts/nexus-operator-checkpoint.py check \
  --checkpoint /private/checkpoints/head-1.json \
  --checkpoint-public-key /private/keys/checkpoint-public.pem \
  --checkpoint-signer-sha256 "$CHECKPOINT_SIGNER_SHA" \
  --trusted-head-sha256 "$LATEST_SHA" \
  --trusted-sequence "$LATEST_SEQ" \
  --sealed /private/transfer/snapshot.sealed
~~~

Explicitly recover after verifying the trusted latest head OUTSIDE the
snapshot host. The scratch and root directories must exist and be private;
the destination must be empty:

~~~bash
python3 scripts/nexus-operator-checkpoint.py recover \
  --checkpoint /private/checkpoints/head-1.json \
  --checkpoint-public-key /private/keys/checkpoint-public.pem \
  --checkpoint-signer-sha256 "$CHECKPOINT_SIGNER_SHA" \
  --trusted-head-sha256 "$LATEST_SHA" \
  --trusted-sequence "$LATEST_SEQ" \
  --sealed /private/transfer/snapshot.sealed \
  --aes-key /private/keys/snapshot-aes256.key \
  --snapshot-signature /private/transfer/signature.json \
  --snapshot-public-key /private/keys/snapshot-public.pem \
  --scratch /private/restore-scratch \
  --root /private/restore-root-empty \
  --approve-recover
~~~

Signed restore retains consumed-approval journal records and refuses replay
of the original execution. It does not restart operator jobs.

## What remains unresolved

The new CLI is intentionally OPTIONAL. Existing legacy unsigned restore,
direct signed restore, and Phase-31 decrypt remain accessible, so there is
NOT platform-wide anti-rollback enforcement. Temp plaintext ZIP cleanup
on normal exit does not ensure secure erasure, avoid encrypted swap concerns,
or cover process/host crash. No transactional rollback of partial restore
writes is promised.

A future release must add an independently controlled nonrewindable latest
head custodian, signer rotation and revocation, review all old restore
entrypoints, demonstrate actual cross-host recovery and isolate key custody.
Do not deploy or merge this stacked draft PR until all exact-head tests and
independent security acceptance pass. Preserve A_out <= A_in.
