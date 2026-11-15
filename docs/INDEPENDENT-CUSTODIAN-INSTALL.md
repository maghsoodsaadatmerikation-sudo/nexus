# Installable independent receiver: code-bundle integrity and root-only deployment

This stage adds an **offline, bounded, deterministic installer** for the Python
code used by the separate NEXUS Ed25519 witness receiver. It installs only
code, and **does not** provision an SSH host, an external custodian, a service,
an account, private keys, any data or immutable/WORM storage.

Use `scripts/workspace-witness-package.py` with explicit commands `build`,
`install`, and `verify`. The bundle contains exactly six allowlisted source
files needed for the standalone receiver:

- `workspace-attestation.py`
- `workspace-trust.py`
- `workspace-offsite-witness.py`
- `workspace-witness-custodian.py`
- `workspace-witness-recovery.py`
- `workspace-witness-host.py`

No repository metadata, arbitrary paths, third-party plugins, application
tokens, private keys, user workspaces or chat history are included. Every file
is encoded in a canonical JSON envelope with its SHA-256 commitment and
strict bounded size.

## 1. Build in a controlled environment

```sh
python3 scripts/workspace-witness-package.py build \
  --source-dir /path/to/a/verified/nexus/scripts \
  --output /private/transport/nexus-receiver-bundle.json

sha256sum /private/transport/nexus-receiver-bundle.json
```

This hash must be verified and **approved independently by the actual
recipient's administrator**, after confirming the source revision/code and
its intended release identity. A SHA-256 printed by the same untrusted
delivery channel is **not** independent authorization or a signature.
Nothing in this tool creates a maintainer release signature or distributes a
trusted digest to another organization.

The bundle is portable to a separate POSIX host with Python3 and OpenSSL.
Transport the exact bundle and independently confirm the approved lowercase
64-character SHA-256 value over a distinct authenticated channel.

## 2. Root-only fresh installation

An administrator on the **separate** recipient host explicitly executes:

```sh
sudo python3 scripts/workspace-witness-package.py install \
  --bundle /private/transport/nexus-receiver-bundle.json \
  --trusted-sha256 YOUR_INDEPENDENTLY_APPROVED_64_HEX_DIGEST \
  --destination /opt/nexus-witness-receiver-v1
```

The installer requires root, verifies the exact canonical bundle and file
hashes **before** making any destination, checks the entire destination's
existing parent path is root-owned, non-group-writable and without symlinks,
then builds the allowlisted files under a private randomly named staging
directory. Files are created exclusively, fsynced, made root-owned and
non-writable by non-root; a root-owned install manifest records the approved
bundle commitment. The directory is renamed into the previously absent
target and its parent fsynced. The installer **never overwrites an existing
deployment**, follows arbitrary archive paths, repairs damaged code or
creates trust keys.

Root-owned installed code is not intrinsically immutable against root
compromise. Protect the host administrator and review software-upgrade
processes. For upgrades, use a new versioned destination and a separate
reviewed cutover; do not replace the active directory in place.

## 3. Independently verify installed code

```sh
python3 scripts/workspace-witness-package.py verify \
  --destination /opt/nexus-witness-receiver-v1 \
  --bundle /private/transport/nexus-receiver-bundle.json \
  --trusted-sha256 YOUR_INDEPENDENTLY_APPROVED_64_HEX_DIGEST
```

**Both original bundle bytes and the independently approved hash are
mandatory.** A self-contained installed manifest is not accepted as sole
authority, because an attacker able to change both installed files and a
manifest could make them agree with one another. The verifier rejects
unexpected files, symbolic/hard links, weak permissions, changed script
content, missing files, changed approved bundle and unsafe directory
ancestry. Verification does not inspect the trust of the installer program
itself: run the installer/verifier from an independently vetted source.

## 4. Dedicated receiver account and SSH authorization

Provision a dedicated unprivileged SSH recipient account **through the host
administrator's existing identity-management process**. Give it only:

- Its own private POSIX receiver-ledger directory (0700), initialized with
  independently approved source and acknowledgment *public* keys
- A separately protected receiver acknowledgment *private* Ed25519 key (0600)
  owned by that recipient account, **outside** its ledger directory
- A root-owned read-only launcher configuration referencing those exact
  absolute paths, as specified in
  [ROOT-PINNED-CUSTODIAN-HOST.md](ROOT-PINNED-CUSTODIAN-HOST.md)

The SSH account must **not** be able to edit installed source, the
administrator's root-owned receiver configuration, SSH daemon settings or
release-bundle approvals. Prevent forwarding, arbitrary shell commands,
user-submitted environment values, writeable authorized_keys wrappers
and unapproved file uploads.

Use a forced SSH command that explicitly launches the installed entrypoint
under **isolated Python mode**:

```text
restrict,command="/usr/bin/python3 -I /opt/nexus-witness-receiver-v1/workspace-witness-host.py serve --config /etc/nexus-witness/receiver.json" ssh-ed25519 AAAA...preapproved-client-key
```

Here the SSH key is deliberately illustrative. Python's `-I` blocks
environment-controlled import paths at startup; the launcher also scrubs
the environment before invoking the fixed custodian CLI. The receiver code
still requires the security administrator to control its installed code
paths and dependencies. The older environment-selected SSH entrypoint must
not be used as the independent host's deployment launcher.

Before enabling SSH traffic, run as the dedicated recipient account:

```sh
python3 -I /opt/nexus-witness-receiver-v1/workspace-witness-host.py check \
  --config /etc/nexus-witness/receiver.json
```

The preflight verifies configuration ownership, ledger structure and full
receipt-signature chain, then confirms that the private recipient signer
matches the public key already pinned by that ledger.

The NEXUS operator must independently enroll the SSH *host public key* in
its pinned known_hosts file, verify the recipient's Ed25519 public key
independently and retain the latest acknowledgment and minimum sequence in
a separate trusted domain. No remote access or publication right is
created by this code-bundle installation.

## 5. Read-only live protocol evidence

After a separate custodian actually receives a signed checkpoint, use
[LIVE-WITNESS-PROTOCOL-GATE.md](LIVE-WITNESS-PROTOCOL-GATE.md) to verify
that the receiver's current SSH `latest` exactly matches an **externally
retained and independently SHA-256-pinned signed package** and the current
NEXUS operator trust state. A successful protocol match is **not proof**
that two different organizations control the host and public keys, nor
that a WORM store, production service or public witness exists.

## 6. Backup, recovery and rollback handling

The independently signed receiver history can be exported/restored using
[CUSTODIAN-DISASTER-RECOVERY.md](CUSTODIAN-DISASTER-RECOVERY.md).
The receiver private key is never included in code or history backups.
A successful code install and preflight do **not** prove that independently
retained latest acknowledgments, separate signing-key custody, disaster
recovery or immutable storage exist.

## CI evidence and remaining boundaries

`scripts/test-workspace-witness-package.py` performs **actual root-owned
installation into a random throwaway /run directory** on a GitHub-hosted
runner. It proves deterministic packaging, refusal of unprivileged install,
wrong digest and duplicate install, verification against the exact approved
bundle, an installed-code preflight with separate disposable real Ed25519
keys, refusal of a root-config ownership violation, refusal of wrong
recipient signer, and rejection of modified code or extra installed files.
Everything is synthetic, and the temporary install is deleted. The prior
real OpenSSH loopback test continues to check host key pinning and recovery.

**No external server, cloud account, independent administrator, production
key custody, real deployment, WORM medium or live user workload was
configured.** A digest checked in the same CI runner as the generated bundle
does not establish a real independent code-approval ceremony. The NEXUS
gateway remains fail-closed on machine-history imports; this installer
does not authorize application runtime access.
