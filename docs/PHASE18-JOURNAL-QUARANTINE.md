# Phase 18 — fail-closed journal quarantine after interrupted jobs

## What changed

A previously consumed approval digest was already non-replayable, but a freshly
prepared plan with a **different** digest could be admitted in the same workspace
while an older job had a persistent `started` journal record. The new policy
closes that loophole. `ApprovalJournal.claim` now checks **all** existing journal
records under the official workspace operation lock before creating a new claim.
If any claim is `started`, **no new digest** may claim that workspace until the
record has a legitimately written terminal receipt. Old claims are never deleted,
changed to success, automatically retried or silently reconciled.

Both the ordinary v3 operator service and opt-in v4 Rootless Job service
preflight the same quarantine before acknowledging a start. Their independent
journal-claim checks remain the final boundary; the CLI's direct engineering
execution also uses the same guarded claim. A read-only `review` or a status
lookup remains available without executing anything.

## Read-only inspection

As a separate local owner, with an existing workspace:

```sh
python scripts/nexus-operator-service.py audit-journal \
  --root /absolute/private/operator-root --workspace alpha
```

A **clear** report returns exit code zero. A **blocked-unfinished** report
returns exit code two and contains only the unfinished SHA-256 approval digests,
finished count and non-authoritative flags. Unknown temporary journal files,
corrupt records, hardlinks, symlinks, unsafe ownership or incomplete `finished`
markers **fail closed** (exit two); no files are cleaned up. No user messages,
command output, plan file names, file contents or credentials are exported.
The audit does not contact Docker or confirm whether a process is still alive.

In particular:

- `recover-stale --acknowledge-possible-orphans` revokes stale **transport**
  files only. It cannot clear the new journal quarantine.
- A started approval after a daemon crash **remains consumed and blocking**,
  even after a new daemon starts and the old socket is revoked.
- Only a legitimately durable terminal receipt written by the original worker
  clears its workspace's blocking state. Do not manufacture one manually.
- An orphaned Docker/container process on the same host is **not** ruled out.
  This is a per-workspace journal guard, **not** host-wide process attestation,
  external kill verification, or a distributed lease. Another workspace can
  operate separately, so operators must still inspect the host for orphans.
- A hostile same-UID process modifying the private journal is outside the
  supported trust model. Host compromise and kernel escape remain untested.

## Acceptance

`nexus-cloud/tests/test_agent_orphan_quarantine.py` covers old started claims
blocking new digests, finished receipts restoring admission, incomplete/dirty
journals, rootless and normal service denial, preserved read-only review/status,
no new workspace created by audit, and independent workspace behavior. The
GitHub **Engineering Agent Contract** runs these alongside existing journal,
service, Docker and rootless acceptance. Do not treat a successful unit suite
as production recovery or safe public deployment. PR #244 remains Draft.
