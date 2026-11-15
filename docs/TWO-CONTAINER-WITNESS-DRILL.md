# Two Docker namespaces: a real SSH integration drill, not a deployed custodian

## Purpose and precise claim

The earlier real OpenSSH test used a single GitHub runner and loopback. This
stage adds a **two-container acceptance test** with separate runtime
namespaces, a dedicated Docker-internal network and distinct Docker volumes
for the NEXUS source, recipient history, recipient signer key and SSH host key.

It tests remote network delivery and recovery **through an actual encrypted
SSH connection** between two isolated processes. A **single Docker daemon and
CI runner still administers both containers**. There is no independent person,
account, country, public host, trusted publication or immutable storage
provider. The test does not demonstrate organizational independence or actual
off-host anti-rollback authority.

## CI-only fixture

- `deploy/witness-ci/Dockerfile` builds a disposable Ubuntu-based image for
  the exercise with OpenSSH, Python and OpenSSL. It is **not** the reviewed
  root-installed release bundle from the previous stage and is **not** a
  production-ready image. Its base reference is a convenience CI tag, not
  an independently pinned release.
- `scripts/test-workspace-witness-two-containers.py` creates a random private
  Docker network with `--internal` and **no ports published on the host**.
  The sender and receiver each execute inside a separate container.
- The **source signer private key** and NEXUS operator trust state remain in
  the sender's `client` volume. The **recipient Ed25519 private key** remains
  in a separate recipient-only signer volume. The receiver's signed
  acknowledgment ledger lives on a different recipient data volume, and
  the SSH host identity in a separate host-key volume. The test explicitly
  checks that the two signing private keys are not mounted into the other
  container.
- The receiver uses the existing **root-owned configuration and
  forced-command SSH entrypoint** with its preflight of pinned Ed25519
  signing-key identity. The sender uses the actual pinned-host
  `workspace-witness-ssh-client.py`. Only source and receiver **public keys**,
  signed receipts and metadata needed for controlled recovery cross
  containers through the disposable test controller.

## Acceptance conditions

The test must demonstrate:

1. A bounded signed source receipt is delivered through the separate
   Docker network over OpenSSH, with the recipient writing and signing its
   acknowledgment using its own private key.
2. Replacing the caller's pinned host-public-key record prevents a valid
   signed acknowledgment from being accepted.
3. A receiver directory backup can be verified against the latest
   independently retained signed package, with no signing key included.
4. The original receiver **data volume is deleted and recreated**; signer
   and SSH host-key volumes are retained separately, emulating their
   independent disaster escrow. The receiver recovers its signed chain
   using the backed-up public ledger and the sender-held latest signed
   receipt, without resetting the sequence.
5. The receiver container is recreated with a different SSH host key.
   Despite having the right recipient signer and signed history, the
   previously pinned client must refuse it. Reconnecting the original
   host-key volume permits authenticated communication again.

All containers, disposable volumes, Docker network and built image are
deleted by the test finalizer. These are synthetic, disposable signing keys
and data with no user information.

## Open operational requirements

A truly independent custodian still needs a separate infrastructure and
administrative authority, a recipient-controlled approved code digest,
a real SSH host with out-of-band pinned host public keys, independent
custody of recipient and source Ed25519 keys, off-host durable retention of
latest acknowledgments and independently approved sequence floors. The test
does not meet any of those cross-organization guarantees.

For a separate real host, follow
[INDEPENDENT-CUSTODIAN-INSTALL.md](INDEPENDENT-CUSTODIAN-INSTALL.md)
rather than using this ephemeral Dockerfile. The existing runtime
`POST /v1/workspaces/import` machine-history refusal remains in force;
passing this test grants no runtime, publication or user-data authority.
