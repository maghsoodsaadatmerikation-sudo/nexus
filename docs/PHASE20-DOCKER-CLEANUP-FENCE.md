# Phase 20 — preserve uncertainty after Docker CLI failure

The operator cannot infer a Docker container's lifetime solely from its CLI
process. Previously, `docker rm -f` errors were discarded, and a plan might
finalize its one-use journal even when the daemon-side container was unknown.

The amended executor uses one Docker environment for `run`, `rm -f`, and
`ps --all --no-trunc --filter id=<cid>`. A missing or corrupt container ID
after a failed CLI, a failed daemon query, or a container still present after
cleanup produces `cleanup-unverifiable`.

Before returning, NEXUS fsyncs a private
`.nexus-docker-unverified-<random>.marker` inside the operator root. The
root-wide journal census validates every marker and blocks approval across
**all** workspaces under that private root, even if the original approval has
a terminal receipt. The audit shows only a marker count; there are no
arguments, command output, mount sources, or secrets.

If even this marker cannot be made durable, the executor raises
`CleanupUnverifiable`; the original one-use journal stays STARTED rather
than being finalized. Interrupted/renamed journals and forged markers are
also rejected, not silently omitted. Evidence is never automatically
deleted, cleared, or converted into a successful outcome.

`audit-host` is observational. There is intentionally **no automatic
unquarantine command** and no assumption that no labelled containers
means there are no orphaned processes. A successful Docker query is evidence
only for one client/daemon context. Old unlabelled containers, alternate
daemons, hostile same-UID processes, or kernel compromise are outside this
claim. Manual independent operator/host investigation remains necessary.
No execution authority is delegated to browser, LLM or public APIs.
PR #244 remains Draft and unmerged.
