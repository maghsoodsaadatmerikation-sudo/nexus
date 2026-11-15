# Pinned SSH receipt handoff and lost-reply recovery (not deployed)

This stage supplies a bounded *transport contract* for the separate Ed25519
custodian introduced in
[INDEPENDENT-WITNESS-CUSTODIAN.md](INDEPENDENT-WITNESS-CUSTODIAN.md).
It does **not** provision an SSH host, create a remote account, configure
authorized_keys, publish receipts, or grant NEXUS runtime authority. The actual
source and recipient must be administered by separate operators.

## Independent custodian SSH setup

On a **separate custodian-controlled host**, initialize the recipient ledger
as described in the prior guide. Use a dedicated system account, private
storage, a recipient Ed25519 signing key under separate custody, and SSH
host-key fingerprints approved *out of band* by the NEXUS operator.

Restrict one SSH authentication key using a **forced command** in
`~/.ssh/authorized_keys`. The command must invoke
`scripts/workspace-witness-ssh-receiver.py` with *no user arguments* and a
known, pinned code path; also apply `restrict` or equivalent
`no-port-forwarding,no-agent-forwarding,no-X11-forwarding,no-pty` and forbid
user-writable changes to the forced-command program. The remote SSH session
may request only the exact commands:

- `nexus-witness-v1 receive`
- `nexus-witness-v1 latest`

Everything else is denied without interpreting arbitrary caller-controlled
shell text. Set `NEXUS_CUSTODIAN_STORE` (absolute receiver-owned private
ledger path) and `NEXUS_CUSTODIAN_ACK_KEY` (absolute separately protected
receiver signing key path) as **trusted server-side configuration**, not
as values accepted from the remote caller.

For example, the custodian's SSH administrator can arrange a fixed
program path with the two environment values set by a protected wrapper.
Neither of these variables should appear in a client-provided SSH command.

```text
command="/opt/nexus/bin/custodian-ssh-entry",restrict ssh-ed25519 AAAA... approved-client-key
```

Where `/opt/nexus/bin/custodian-ssh-entry` is installed/owned by the
custodian administrator and execs the fixed Python receiver with the
server-configured paths. The `ssh-ed25519 ...` value above is **illustrative**,
not an actual registered key.

**Important**: The forced command and storage paths are security sensitive.
Do not grant arbitrary shell, SCP/SFTP, agent forwarding, port forwarding or
write access to receiver code to this dedicated SSH user. The receiver relies
on the SSH daemon for real host-key checking and authenticated client access.

## Client transport commands

After independently obtaining and verifying the remote server's SSH host key,
put its exact line into an **operator-controlled** `known_hosts` file. Do not
trust a newly discovered host key from the same unverified transport channel.
Use an SSH identity key restricted to the independent receipt receiver.

The client forces `StrictHostKeyChecking=yes`, `BatchMode=yes`, an explicit
`known_hosts` file, no global SSH configuration, identity-only authentication,
no agent, no forwarding, no ProxyCommand/ProxyJump, no connection reuse, and
a fixed two-command protocol. It refuses missing/unsafe key files.

Send an already signed state receipt:

```sh
python3 scripts/workspace-witness-ssh-client.py send \
  --host witness.example.org --user receiptadmin --port 22 \
  --known-hosts /protected/receipt-hosts \
  --identity /protected/receipt-ssh-key \
  --receiver-id independent-organization-1 \
  --source-key-id rollback-2026-a \
  --source-public-key /trusted/rollback-signer.pub.pem \
  --ack-key-id custodian-2026-a \
  --ack-public-key /trusted/custodian.pub.pem \
  --minimum-sequence 42 \
  --state-dir /private/nexus-operator-trust \
  --receipt /private/checkpoint-000042.json \
  --output /protected/ack-checkpoint-000042.json
```

Retrieve the receiver's latest signed package:

```sh
python3 scripts/workspace-witness-ssh-client.py latest \
  --host witness.example.org --user receiptadmin \
  --known-hosts /protected/receipt-hosts \
  --identity /protected/receipt-ssh-key \
  --receiver-id independent-organization-1 \
  --source-key-id rollback-2026-a \
  --source-public-key /trusted/rollback-signer.pub.pem \
  --ack-key-id custodian-2026-a \
  --ack-public-key /trusted/custodian.pub.pem \
  --minimum-sequence 42 \
  --state-dir /private/nexus-operator-trust \
  --output /protected/latest-ack-000042.json
```

The destination file must be **new** and is saved as private, fsynced JSON;
existing acknowledgment paths cannot be overwritten. The client verifies
both **the signed source state receipt and the recipient's signed
acknowledgment**, the preselected receiver identity and minimum sequence,
and optionally the current NEXUS trust-state commitment. A `send` response
must contain the **same** source receipt that was submitted.

## Recovery and failure conditions

The receiver commits/fsyncs its ledger **before** returning the signed
acknowledgment. If the SSH connection drops after commit, client status is
**UNKNOWN**, not "failed to record". Retry the **exact same receipt**:

- If it is still the receiver's latest entry, `receive-stdin` returns that
  previously signed acknowledgment without creating a new sequence.
- If the receiver has advanced beyond it, the old receipt is denied. Use
  the separate `latest` command to retrieve the latest signed state, compare
  it to trusted local checkpoint records, and reconcile manually. The
  receiver does **not** manufacture an earlier acknowledgment.
- If the server returned an invalid signature, changed receipt or an
  acknowledgment with a sequence below the caller's pinned floor, client
  refuses success and writes no acknowledgment file.
- If the local trust state legitimately changes, an old receipt cannot be
  treated as current. Produce, send and independently acknowledge a new
  receipt using the security process in the prior stage.

**A pinned minimum sequence remains an independent operator responsibility.**
A stale receiver compromised along with the client's pinned sequence state
may still present valid older signed packages. The receiver ledger is not WORM
and the protocol does not establish an independently trusted timestamp.

## Limits and tests

- Only bounded witness receipt JSON crosses SSH stdin. **No raw Workspace,
  chat history, signing key, NEXUS bearer token or API mutation** is sent.
- The two allowed remote operations are fixed; the remote script refuses
  unexpected `SSH_ORIGINAL_COMMAND` and sessions without `SSH_CONNECTION`.
- The client requires SSH host identity and signed Ed25519 acknowledgment;
  host trust must be independently enrolled before connecting.
- `scripts/test-workspace-witness-ssh.py` runs the actual Python client and
  forced-command receiver against real disposable Ed25519 keys but uses a
  **fake local SSH executable** to simulate authentication results and
  interruptions. It asserts safe OpenSSH options and tests post-commit reply
  loss, exact-latest retry, replay, fabricated remote response and unsafe SSH
  key material. It does **not** establish that a real SSH daemon, network,
  remote trust host, WORM medium or disaster-recovery drill exists.
- There is no automated service deployment, cloud provider, SMTP/webhook,
  secret creation, remote side effect, new HTTP route or production mutation.
  NEXUS `POST /v1/workspaces/import` still rejects external machine history.

The next operational milestone needs an explicit independent provider/custodian
and a real SSH host, host-key ceremony, private-key rotation and controlled
crash/recovery test before any production anti-rollback claim is justified.
