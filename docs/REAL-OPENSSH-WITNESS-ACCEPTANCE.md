# Real OpenSSH loopback acceptance for NEXUS witness custody

## What changes

The prior SSH handoff proof in
[PINNED-SSH-WITNESS-HANDOFF.md](PINNED-SSH-WITNESS-HANDOFF.md)
used an executable named `ssh` that simulated success and failure. That
covered command construction and Ed25519 response validation but could **not**
prove that a genuine SSH daemon performed cryptographic host authentication
or enforced the authorized_keys forced-command policy.

`scripts/test-workspace-witness-ssh-real.py` now executes a disposable **real
OpenSSH server** bound only to `127.0.0.1` on an ephemeral high port during
GitHub PR verification. All source, receiver, OpenSSH client, OpenSSH host,
and Ed25519 signer keys are generated for this test alone, within a temporary
0700 directory in the runner's home. The test uses a temporary
`authorized_keys` file with the SSH `restrict,command="..."` policy. Nothing
is installed in the operator's existing `~/.ssh` or saved to a repository,
remote host, cloud service or artifact.

## What the test proves

1. A real OpenSSH transport exchanges an Ed25519-signed state receipt over
   stdin to the custodian's strict forced-command receiver.
2. The client's independent verification of the source and acknowledgment
   Ed25519 signatures accepts the resulting signed receipt package.
3. A wrongly pinned SSH **host public key** and a client authentication
   identity not present in `authorized_keys` fail without an acknowledgment.
4. An authenticated SSH client attempting a nonallowlisted remote command
   is rejected by the forced-command entrypoint.
5. A controlled fault suppresses the SSH response **after** the receiver
   has fsynced the new receipt; the client reports an unknown outcome and
   writes no acknowledgment output.
6. Retrying the exact signed receipt through a new SSH connection returns
   precisely the prior signed package. It never advances the custodian
   sequence. Replaying an older receipt after a newer one is accepted fails.
7. The SSH daemon is stopped and restarted, preserving the independent
   custodian's durable local state. An offline request fails, while a
   post-restart latest query returns the same signed receipt.

The test runs in the read-only PR workflow with unprivileged HTTP-like
network access restricted to the runner's own loopback. An ephemeral SSH
daemon requires `sudo` to authenticate the runner account; the script
terminates it and cleans up the temporary directory in its finalizer.
The PR job installs the OS package `openssh-server` if it is absent.

## Boundaries

**This is a real SSH integration test, not a real external custodian
deployment.** Both processes still run on the same GitHub-hosted CI machine,
and all cryptographic keys, disks and SSH daemon identities are disposable.
No external host key ceremony, independent retention, remote organization,
public endpoint, cloud provider or live receiver account is established.

The test validates the OpenSSH client-server handshake and forced-command
policy, but does not prove that all required controls are configured on a
different production host. The receiver ledger is not WORM storage; external
custody is still needed to resist an attacker who controls its operating
system. The NEXUS Rust/API trust boundary remains unchanged:
`POST /v1/workspaces/import` still denies external machine-history claims.

CI workflow permissions remain `contents: read`; no repository or release
publishing privileges were introduced.
