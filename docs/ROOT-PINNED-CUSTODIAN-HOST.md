# Root-pinned independent witness SSH receiver: deployment preflight

**Deployment-ready code; no independent host has been provisioned.**

The earlier `workspace-witness-ssh-receiver.py` selects the ledger and
acknowledgment signer private-key paths from environment variables. That
legacy entrypoint is retained for simulated transport fixtures only and
**MUST NOT be used in an independent-host deployment**. SSH servers may
permit client-supplied environment variables or mutable authorized_keys
wrappers; accepting security-critical paths from such environment is unsafe.

Use **`scripts/workspace-witness-host.py`** as the forced-command entrypoint.
It reads the receiver ledger and signer identity solely from a root-owned
declarative configuration whose **exact path is fixed by an administrator**
in the SSH forced-command policy.

## Verified code installation

For a bounded root-only installation of the complete receiver source tree,
follow [INDEPENDENT-CUSTODIAN-INSTALL.md](INDEPENDENT-CUSTODIAN-INSTALL.md).
The original independently approved code-bundle bytes and SHA-256 digest
are both required for subsequent integrity checks. An installer manifest
stored beside the code is never an independent source of trust. Use the
root-installed launcher with Python isolated mode (`-I`) for the SSH
forced command; no real external host is provisioned by the repository.

## Host configuration

On a separate host administered outside NEXUS, install the program and all
Python dependencies at a root-owned, non-writable and pinned code path. Set up
a dedicated unprivileged SSH account for the witness, and provision a private
receiver directory (0700) and a **separately** protected Ed25519 recipient
private key (0600), both owned by that account. Initialize the receiver
through `workspace-witness-custodian.py init` using out-of-band approved
public keys. The recipient's private key must match the public key pinned in
that receiver's trusted ledger. Store the private key **outside** the ledger
directory so that a public-history backup cannot accidentally contain it.

An administrator creates a **root-owned configuration** at a path such as
`/etc/nexus-witness/receiver.json` (the file and **every parent directory**
must belong to root, be non-writable by group/others and be free of symlinks).
Example with illustrative paths only:

```json
{
  "schema": "nexus.offsite.root-pinned-launch.v1",
  "store_dir": "/var/lib/nexus-witness/receiver",
  "ack_private_key": "/var/lib/nexus-witness-keys/receiver.private.pem"
}
```

The configuration is metadata only; no keys or user data are embedded.
The file must be root-owned, have one link, be no larger than 4 KiB and
not be group/other writable. No security-relevant path may come from
`SSH_ORIGINAL_COMMAND`, `AcceptEnv`, the remote JSON input or shell
expansion. A compromised unprivileged receiver account should not be able
to replace its own root-pinned launch config.

Run **as the dedicated receiver account** to verify readiness before
accepting SSH traffic:

```sh
python3 /opt/nexus-witness/workspace-witness-host.py check \
  --config /etc/nexus-witness/receiver.json
```

The preflight validates root ownership and non-writable path ancestry,
strict JSON schema, private receiver directory and receiver ledger, every
previous source/receiver Ed25519 signature, the separately protected
private key and its actual match to the ledger's pinned public key. It
does not create an SSH account, provision a private key or open a port.

Configure the receiver's `~/.ssh/authorized_keys` **by the independent
host administrator**, with a single approved public client SSH identity
and a forced command containing the fixed full configuration path:

```text
restrict,command="/usr/bin/python3 /opt/nexus-witness/workspace-witness-host.py serve --config /etc/nexus-witness/receiver.json" ssh-ed25519 AAAA...approved-receipt-sender
```

The placeholders are not real keys. The receiver must run under a
separate unprivileged account whose login shell / sshd policy does not
allow arbitrary commands, port forwarding, agent forwarding or file
uploads. The forced command accepts only the two exact
`SSH_ORIGINAL_COMMAND` values `nexus-witness-v1 receive` and
`nexus-witness-v1 latest`, and requires `SSH_CONNECTION`. Any other
request fails without command or path interpolation. The launcher
executes only the fixed Python custodian CLI with a scrubbed process
environment and a fixed binary path.

## Operational security and boundaries

- **Do not send the private receiver key, NEXUS data keys, user files or
  authorization tokens to the SSH sender.** Only bounded signed source
  receipts and signed acknowledgments may cross this transport.
- Restrict filesystem paths containing program code and receiver configuration
  against writes by the SSH account. The launcher checks configuration
  ancestry but is **not itself a secure software installer** or executable
  integrity attestation. Pin and verify its code separately.
- The SSH client's `known_hosts` and the receiver public key must be
  enrolled using a distinct trusted channel; host key changes require
  independent reapproval.
- This stage does not create a real separate host, account, remote key
  custody, external WORM retention, live network tunnel or administrator.
  A GitHub Actions loopback exercise is not a production deployment.
- The receiver history remains mutable by an attacker controlling its
  operating system. Independently held signed latest acknowledgments and
  minimum-sequence floors are still required for rollback detection.
- NEXUS `POST /v1/workspaces/import` remains fail-closed for unattested
  machine histories. The new receiver **does not grant runtime import,
  human decision or publication authority**.

## CI proof

The real OpenSSH loopback integration now creates a temporary root-owned
configuration directory under `/run`, uses it from the authorized_keys
forced command, and passes deliberately incorrect legacy environment paths
to ensure they cannot override the root-pinned store/key. Tests reject a
user-owned configuration before attempting to establish transport. The
existing real SSH suite continues to verify host-key pins, unauthorized
client access, command allowlisting, post-commit lost-reply retry, total
receiver directory loss, independently anchored restore and daemon restart.
All temporary test directories, keys and sshd processes are removed; this
is not an external witness-custodian deployment.
