# Independent off-host witness for NEXUS trust-state rollback detection

## Problem addressed

The operator's \`trust-state.json\` is fsynced and protected by local ownership,
locking and monotonic event/content anchors. However, an attacker with access
sufficient to **restore the entire trust directory to a previous valid
version** can bypass checks stored in that same directory.

A different custodian must retain the **most recent** checkpoint, beyond the
attacker's ability to replace or delete it. This stage implements the
cryptographic *receipt and comparison* protocol; it **does not connect,
configure, or claim any remote WORM/immutable storage service**.

## What the independent receipt proves

The new tool \`scripts/workspace-offsite-witness.py\` produces a small, detached,
Ed25519-signed v1 receipt containing:

- A domain-separated algorithm, receipt schema and role
  \`external_state_witness\`.
- An explicitly identified **independent witness signer**, plus the SHA-256
  fingerprint of its public key.
- SHA-256 and byte length of the **canonical, validated local trust state**,
  including pinned public keys, active/revoked statuses, each workspace's
  event and content checkpoints and signer IDs.
- Aggregate key/workspace counts and a random checkpoint nonce.

**No workspace ID, question, claim text, source, private key or raw snapshot
is included in a receipt.** The signature covers the complete canonical
receipt body, prefixed by an exclusive binary domain. The trust state is
validated under its existing POSIX lock; neither command changes that state.
Public signing keys are selected separately from the untrusted receipt.

A receipt only proves that a holder of the separate witness private key signed
this particular state commitment. It is not a timestamp, proof of historical
machine execution, immutable storage, independent key custody or proof of
an actual public publication.

## Example: private local operator + separately controlled recipient

Generate a **separate** witness keypair through your approved custody process,
not in NEXUS, and independently distribute/pin the *public* key and key ID.
For a temporary test key only:

```sh
openssl genpkey -algorithm ed25519 -out /separate-custody/rollback.pem
chmod 600 /separate-custody/rollback.pem
openssl pkey -in /separate-custody/rollback.pem -pubout \
  -out /recipient/rollback.pub.pem
```

After **every change** to the operator trust state (enrollment, revocation,
rotation, successful witness record or legacy \`anchor\`), create a **new
uniquely named** receipt outside the trust directory:

```sh
python3 scripts/workspace-offsite-witness.py seal \
  --state-dir /private/nexus-operator-trust \
  --witness-key-id rollback-2026-a \
  --witness-private-key /separate-custody/rollback.pem \
  --output /pending-external-copy/checkpoint-000042.json
```

**Explicitly send the newly created receipt** to a distinct
administrator/organization or store it in independently controlled append-only
or WORM storage, **then require acknowledgment** that it was durably retained.
The tool intentionally does not call any remote API or automatically send data.
A local \`/pending-external-copy\` directory alone is **not** an independent
witness, even if the files are signed. Do not overwrite or delete an earlier
receipt. Use an operator process to maintain an independently approved ordering
and identify the *latest acknowledged* checkpoint.

From the independent recipient's copy, one can verify its signature even
without having the NEXUS trust directory:

```sh
python3 scripts/workspace-offsite-witness.py verify-receipt \
  --receipt /recipient/latest-acknowledged.json \
  --trusted-key-id rollback-2026-a \
  --trusted-public-key /recipient/rollback.pub.pem
```

Before relying on local trust state, compare it with that **latest external**
receipt:

```sh
python3 scripts/workspace-offsite-witness.py check \
  --state-dir /private/nexus-operator-trust \
  --receipt /recipient/latest-acknowledged.json \
  --trusted-key-id rollback-2026-a \
  --trusted-public-key /recipient/rollback.pub.pem
```

A match proves only that the current, semantically validated trust-state
commitment **equals the independently retained checkpoint**. An older but
internally consistent registry, a deleted/revoked key reappearing, or altered
checkpoints cannot match the latest receipt. A legitimate change after the
receipt is also a mismatch: **do not ignore the failure**. Seal and externally
acknowledge the new state, then use that receipt as the new latest reference.

## Threat boundaries and deployment requirements

- No off-host witness is actually published or held independently by this PR.
  **Actual anti-rollback assurance depends on a second trust domain**
  retaining the latest receipt and its pinned signer key securely.
- A compromise of both the NEXUS state and external witness private key or
  latest-receipt custodian can defeat this mechanism. Keep the witness key
  separate from all existing machine-history Ed25519 keys; the tool refuses
  a signer whose public key is present in the local NEXUS data-key registry.
- The check intentionally does **exact equality** rather than falsely
  accepting any purported newer local version. A signed older checkpoint is
  not freshness evidence. No trusted clock, sequence service or independent
  append-only order is implemented here.
- Verification of a receipt signature **alone** does not verify current
  trust state. \`check\` must read the validated trust registry and compare
  every committed state field.
- Do not store the signing private key, live trust directory or latest
  authoritative receipt in Git, the public browser, production container
  images, untrusted CI or a developer-controlled mutable folder. CI generates
  and discards synthetic private keys and never publishes a real receipt.
- NEXUS still **rejects** third-party machine-history import through
  \`POST /v1/workspaces/import\`, and neither receipt creation nor validation
  grants deployment, human judgment, key enrollment or execution privileges.
- POSIX local-filesystem semantics, bounded inputs and caller-pinned
  executable/public key are required. Do not interpret successful CI tests as
  production storage durability, distributed consensus or third-party audit.

## Regression

Run \`python3 scripts/test-workspace-offsite-witness.py\`. The test creates
ephemeral real Ed25519 keys and a disposable local trust state, records and
externally copies signed receipts in a simulated independent folder, then:

- Accepts an exact, independently signed current state.
- Rejects a rollback to a previously valid but older trust state.
- Rejects unexpected legitimate revisions until a newer receipt is acknowledged.
- Rejects an altered digest, signer ID, role, signature, ambiguous JSON, wrong
  public key, reused data-witness signer, unsafe private key permissions and
  symlink/hardlink substitutions.
- Confirms concurrent writes cannot overwrite a single receipt filename.

These tests run in the normal PR verification workflow with synthetic data
only; they do not establish or manage any remote witness custody.
