# Independent receiver: live cryptographic protocol gate

## Why this gate exists

The CI/loopback and two-container tests prove the **mechanics** of verified
OpenSSH and Ed25519 acknowledgments. They do **not** prove that a receiver
actually runs on an independently controlled external account. An old but
valid signed receipt, or the same administrator's Railway/NEXUS host, must
not be silently promoted to independent custody evidence.

`scripts/workspace-witness-live-gate.py` provides a **read-only, fail-closed
live protocol check**. It checks that the remotely queried latest receipt
matches the **exact already retained and separately SHA-256-pinned package**
and matches the currently validated local trust state. Successful output
is deliberately classified as `cryptographic_protocol_match`, **not**
"independent", "production ready", "deployed" or "immutable storage".

## Independent approval prerequisites

Before using this tool outside a synthetic environment, the source operator
and a separately controlled custodian must complete the following through
their own authenticated, out-of-band process:

- Identify and verify the **external SSH host key fingerprint** and install
  it into an operator-controlled `known_hosts`; do not learn the SSH host key
  from the untrusted first network connection.
- Independently pin the source's and recipient's **different Ed25519
  public keys**, their key IDs and the expected receiver ID.
- Obtain and independently retain the recipient's newest **signed package**,
  along with an independently approved SHA-256 of its exact bytes and a
  **minimum receipt sequence** from outside the NEXUS trust state.
- Retain the external signed checkpoint and its sequence floor in a trust
  domain which cannot be rewritten together with NEXUS (e.g. independent
  recipient administrative custody). A checkpoint copied to a second folder
  on the same compromised host **is not independent**.
- Establish separately who administrates and pays for the custodian host,
  what durable retention and backups exist, and how the custodian handles
  loss, resignation, revoked keys or compromise.

**Neither this tool nor GitHub CI can automatically establish any of those
organizational facts.** Do not treat a project under the same administrative
Railway/Render/GitHub account as an independent custodian solely because it
runs on another VM or has a different name.

## Live protocol comparison

All values and paths below are illustrative. Only run after obtaining
explicitly approved host and public keys and the independent signed package.

```sh
sha256sum /separately-retained/latest-signed-package.json

python3 scripts/workspace-witness-live-gate.py \
  --host verified-external-witness.example.org \
  --user witness \
  --port 22 \
  --known-hosts /approved/witness-known-hosts \
  --identity /private/witness-client-ssh-key \
  --receiver-id independently-approved-receiver-id \
  --source-key-id approved-source-key \
  --source-public-key /approved/source-ed25519.pub.pem \
  --ack-key-id approved-recipient-key \
  --ack-public-key /approved/recipient-ed25519.pub.pem \
  --minimum-sequence 42 \
  --state-dir /private/nexus-operator-trust \
  --trusted-package /separately-retained/latest-signed-package.json \
  --trusted-package-sha256 APPROVED_EXACT_PACKAGE_SHA256_HEX \
  --report /private/new-witness-protocol-evidence.json
```

The program refuses success or output unless all of the following are true:

1. The checkpoint is outside the local trust directory and exactly hashes
   to the **independently supplied expected package digest**.
2. The retained checkpoint validates the source Ed25519 signature, recipient
   Ed25519 acknowledgment signature, preapproved receiver/key IDs, and
   pinned minimum sequence.
3. The same checkpoint matches the current locked, validated local NEXUS
   trust-state commitment (size, hash and key/workspace counts).
4. The pinned SSH client makes a **read-only** remote `latest` request with
   strict host-key checking, no SSH agent, forwarding, proxies or user
   configuration, and validates both signatures of its answer.
5. The live remote package agrees **exactly** with the independently retained
   reference; an older/forked/newer unexpected state fails closed.
6. The evidence path is an **unused absolute path**, outside the local trust
   directory; it is written exclusively and fsynced only after all checks.

The evidence report contains only identities, signatures' digests, state
commitment, approved checkpoint digest, known-hosts file digest and checked
conditions. It contains **no private key, raw workspace, conversation, bearer
token or command execution authority**. Its outcome explicitly states:

```json
{
  "result": "cryptographic_protocol_match",
  "external_administrative_independence": "not_verified",
  "immutable_retention": "not_verified",
  "production_deployment": "not_verified",
  "machine_history_import_authorized": false
}
```

That JSON is *illustrative* of report fields, not an exact schema instance.
The report is **not cryptographically signed** and can be modified by someone
who controls its local file. It is an operator-observation aid, never an
independent witness or release permit.

## Failure handling

Any of these conditions prevents a positive result: missing/wrong SSH
host-key pin, invalid recipient signature, changed public key or receiver ID,
stale accepted sequence, source-state rollback, stale external package,
changed externally pinned bytes, duplicate-key JSON, a checkpoint stored
within the local registry, a pre-existing output path or an unavailable
receiver. The tool makes no attempt to repair the ledger, enroll a new key,
accept a changed host identity, resend a receipt, modify NEXUS history or
quietly lower the minimum sequence.

**A legitimate new NEXUS trust-state change will fail against the prior
checkpoint** until that new state has been independently accepted and a new
reference is approved. Do not override the test to accept a newer unapproved
remote response. Use the signed acceptance and recovery workflow to reconcile
a discrepancy under independent custody.

## Verification scope

The real OpenSSH integration test in
`scripts/test-workspace-witness-ssh-real.py` now exercises a matching external
package with a separate SHA-256 commitment, as well as wrong package hash,
minimum sequence, receiver identity, host-key pin, local trust state, and
a pretend external reference stored inside the local trust directory.
The probe is also covered indirectly by the normal PR verification gate.

These are disposable test keys and localhost SSH. **No independent external
receiver has been connected or attested, no operational host has been changed
and no new NEXUS import authority has been granted.**
