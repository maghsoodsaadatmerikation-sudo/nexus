# Phase 17 — crash supervision and explicit owner-only transport recovery

The **single-owner, unprivileged** operator service now holds an exclusive,
owner-only, private-root `.nexus-operator.lock` for its lifetime. A second daemon
cannot start over the same root. During graceful shutdown it signals running
jobs to stop and joins worker threads before releasing the lock. If any worker
fails to terminate within the bounded shutdown period, the lock remains held
until the host process exits; the service must **not** suggest that restart is
safe while a guest or container may still be active.

The rootless guest launcher installs Linux `PR_SET_PDEATHSIG=SIGKILL` in a
separate trusted Python process before `execve('/usr/bin/unshare')`. It also
checks that the originally recorded parent PID still exists immediately after
setting the signal, to close the setup race. There is no `preexec_fn` in the
threaded server. `unshare --kill-child` is still required to terminate its
child PID namespace when the supervised unshare process dies. Negative tests
actually SIGKILL the controlling parent and verify that a waiting child does
not complete. This is **not** proof against host-root, hostile same-UID code,
all kernel vulnerabilities, daemon process-group tampering, or every possible
subprocess escape. The manually invoked regular Docker executor does *not*
acquire the new rootless-only PDEATHSIG guarantee.

If a daemon is killed abruptly, its private Unix socket and 256-bit token are
left behind. Startup deliberately fails instead of reusing those credentials.
There is no automatic retry or deletion of durable single-use journals.
After inspecting potential orphan processes on the machine, a trusted local
operator may explicitly revoke **only** the stale transport files:

```sh
python scripts/nexus-operator-service.py recover-stale \
  --root /absolute/private/operator-root \
  --acknowledge-possible-orphans
```

Recovery requires a private-root flock, validates the token's owner, inode,
mode, length and format, and requires a stale Unix socket that refuses a
connection. Live services, corrupted tokens, symlinks, hardlinks and uncertain
socket errors are rejected without deleting evidence. The file holding the
flock stays on disk; it is deliberately never deleted. A recovery receipt
reports `journal_preserved: true`, `jobs_restarted: false`, and
`orphaned_processes_ruled_out: false`.

**Warning:** this command does *not* terminate orphaned Docker/guest processes,
resolve the result of a journal left in the `started` state, or authorize new
execution. It solely revokes stale socket/token credentials. An operator must
inspect host processes and all outstanding journal states independently before
restarting or promoting a service. An interrupted digest is consumed forever;
preparing a new plan requires a new explicit independent human approval.

A real Linux SIGKILL acceptance test verifies stale-token recovery, unchanged
journals, refusal to replay a consumed digest, and fresh token creation only
by a separately started owner-only daemon. It also tests live-socket refusal,
corrupted file refusal, explicit CLI flag enforcement and graceful worker join.
This remains a **draft, non-deployed** control plane, with no browser-to-Unix
socket, model-initiated execution, or multi-tenant execution enabled.
