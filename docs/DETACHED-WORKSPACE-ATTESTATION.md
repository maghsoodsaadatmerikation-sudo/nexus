# Detached Ed25519 workspace attestation — operator-side only

## What is implemented

The tool `scripts/workspace-attestation.py` signs or verifies the **exact UTF-8
JSON file bytes** of a version-1 NEXUS workspace snapshot containing machine
provenance. Signatures are stored in a separate bounded JSON sidecar containing:

- `schema = nexus.workspace.detached-attestation.v1`
- `algorithm = Ed25519`
- `key_id` and `destination_workspace_id`
- `snapshot_size_bytes`, `snapshot_sha256`, and `signature_base64`

The signed preimage is a fixed binary domain separator followed by four
8-byte-big-endian length-prefixed fields, in order: UTF-8 key ID, UTF-8
workspace ID, 32-byte SHA-256 digest and the **original snapshot bytes**.
No JSON re-serialization or normalization occurs. Even whitespace edits break
the signature. Destination and signer identity are bound to the signature.
Duplicate JSON keys and non-finite numeric values are rejected.

The CLI uses OpenSSL's native Ed25519 implementation, not custom public-key
cryptography or new Rust dependencies. Verification never accesses a private
key. The operator supplies a **trusted public key independently** of the
snapshot and sidecar; the sidecar cannot enroll its own key. Snapshot size is
bounded at 16 MiB and the sidecar at 8 KiB. The tool creates a new sidecar
exclusively rather than overwriting any earlier witness.

## Usage on a private operator machine

Use an approved protected signing key. For **local testing only**:

```sh
openssl genpkey -algorithm ed25519 -out /secure/operator.pem
chmod 600 /secure/operator.pem
openssl pkey -in /secure/operator.pem -pubout -out /secure/operator.pub.pem
```

Sign an export containing machine history:

```sh
python3 scripts/workspace-attestation.py sign \
  --snapshot /private/export.json \
  --workspace-id original-workspace-id \
  --key-id operator-key-v1 \
  --private-key /secure/operator.pem \
  --output /private/export.attestation.json
```

Verify, selecting the public key from an **independently trusted** source:

```sh
python3 scripts/workspace-attestation.py verify \
  --snapshot /private/export.json \
  --attestation /private/export.attestation.json \
  --expected-workspace-id original-workspace-id \
  --trusted-key-id operator-key-v1 \
  --trusted-public-key /secure/operator.pub.pem
```

Signing and verification are manual, local operator actions. **Never place**
a private key in Git, CI, a browser, logs, a container image, or an HTTP
endpoint that accepts user-controlled content for signing. Regression tests
generate ephemeral keys inside temporary directories and then discard them.

## Crucial limits

**A verified signature is not permission to import.** Existing
`POST /v1/workspaces/import` still rejects incoming machine history with
`unattested_machine_history_rejected`. No runtime route, database schema,
existing snapshot, HTTP trust check or production service changes in this PR.

This CLI verifies a detached signature over exact content and destination.
It does **not** prove that the named machine actually ran, perform the complete
Rust workspace semantic validation, establish a trusted-key registry, or keep
durable anti-replay state. In particular, a previously valid signed export
may be replayed on an otherwise empty installation without a separate
trusted revision ledger. Key custody and source evidence require independent
operator verification.

An optional **operator-side public-key registry and monotonic offline witness
ledger** is now available. See [OPERATOR-WORKSPACE-TRUST.md](OPERATOR-WORKSPACE-TRUST.md).
It verifies using enrolled public keys, supports revocation and key rotation,
and prevents replay or event-prefix rewrites **within its private local state**.
It does not give the HTTP gateway authority to import signed machine history
or protect against an operator-level rollback of the whole trust directory.

Before signed imports can be enabled, NEXUS still requires:

1. An operator-owned trusted public-key registry, scoped signer roles,
   revocation, key rotation, and compromise recovery.
2. Server-side Rust snapshot validation before any import write.
3. A durable monotonic anti-replay/revision ledger bound transactionally to
   the target workspace, including rollback and restoration handling.
4. A threat-model review of private-key custody and actual source adapter
   execution attestation.
5. Separate permissions for historical evidence, execution, and decisions.

Until then, a signed history is an **offline integrity witness**, not trusted
runtime input. Human-reported model outputs remain explicitly unverified
`ExternalEvidence`.

## Regression and CI

Run `python3 scripts/test-workspace-attestation.py`. This creates two disposable
real Ed25519 keypairs and verifies correct signatures, whitespace/content
alteration, substituted keys/key IDs, wrong workspace, schema or algorithm
changes, forged signatures, non-unique JSON fields, non-machine imports and
exclusive sidecar creation. The existing PR verification gate runs this test
without publication privileges, network access or persistent keys.
