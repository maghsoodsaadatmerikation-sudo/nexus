# Phase 19 — operator-root-wide quarantine and observational host inventory

## Behavior and safety boundary

An interrupted approval (`state=started`) in **any workspace sharing the same
private operator root** now quarantines *every* new execution under that root.
This holds for both v3 engineering plans, v4 Rootless Jobs, and direct local
`execute_plan`: the check is inside `ApprovalJournal.claim` before any side
effect. A durable 0600 `.nexus-agent-host-admission.lock` serializes competing
claims across different workspaces, preventing two independent admissions from
both observing an empty journal. The original workspace lock is still held.

The owner-only host census validates all journal directory names and ownership,
all workspace directories, and every private journal record; malformed or
incomplete receipts, symlinks and unexpected atomic-write files cause a
fail-closed admission denial. `finished` does not certify that an old Docker
container or guest is gone. No record is removed, modified, or relabelled by
audit; there is **no manual bypass and no automated quarantine lifting** of
unfinished claims. A legitimate worker may write a finished record while still
active in its cleanup path; host-only process/lifecycle verification remains
separate and cannot be inferred from a journal.

The host-scope here means **the single 0700 operator root**, not all user
accounts, Docker contexts/daemons, Linux processes or machines. Other private
roots do not share an approval ledger. Same-UID hostile processes, privileged
host users and out-of-band Docker clients remain outside this contract.

## Independent read-only host observations

```sh
python scripts/nexus-operator-service.py audit-host \
  --root /absolute/private/operator-root
python scripts/nexus-operator-service.py audit-host \
  --root /absolute/private/operator-root --inspect-docker
```

The first command inspects the root's durable local journal evidence; it
creates/uses an owner-only **flock metadata file**, but does not create any
workspace or modify approvals. The second additionally asks Docker for an
**observational, read-only** list of containers carrying the fixed
`nexus.operator.managed=1` label, using `docker ps --all --no-trunc` and no
remove, stop, exec or privileged operation. All new NEXUS `run_container`
executions apply this label. Historic unlabelled containers or another Docker
context are **not** ruled out. If the Docker CLI/daemon is absent or returns
malformed or excessive output, the observation is `unverifiable`, not PASS.
Only 64-hex container IDs and counts are returned; no command, image,
mount source, environment or stdout are exported. This is not a cryptographic
signature, inventory attestation or reason to clear quarantine.

The `audit-host` command returns exit code 2 on a blocked journal or on a
requested Docker inventory with labelled containers or unverifiable results.
It does not restart an interrupted plan, reconcile a crashed journal, remove
or kill a container, reissue an approval, authorize a guest or change a daemon
configuration. The report permanently sets
`orphaned_processes_ruled_out=false` and `production_attested=false`.

CI unit tests cover cross-workspace admission denial, concurrent different
workspace claims, hardlinks/symlinks/malformed journals, read-only Docker
inventory and default-unverifiable status. The existing real Docker acceptance
covers running containers but cannot certify any production Docker host.
Keep PR #244 Draft and unmerged pending independent host-security validation.
