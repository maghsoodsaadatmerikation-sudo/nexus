# NEXUS Phase 13 — restricted tenant tool admission and group hardening

**Development acceptance only. Not a production multi-tenant security claim.**

## Changes

- The strict tenant service (`scripts/nexus-tenant-service.py`, which starts `OperatorServer(allow_container=False)`) **refuses the entire plan** before any one-use approval is claimed if any step uses `run`, `research`, or `package`. That includes mixed plans that start with an otherwise-allowed write. Read-only `review` can describe an unsupported step but is never execution permission.
- The six workspace-bound step types remain eligible for separately approved local execution: `read`, `write`, `edit`, `verify_sha256`, `search`, `preview_edit`. New tool types are not automatically granted; a regression test compares the complete parser tool set against this allowlist and the explicit denylist.
- Strict tenant start-up checks `os.getgroups()` and refuses any group other than its own primary GID, including dangerous host groups such as Docker, LXD or disk. An empty supplementary-group list or a list containing only the primary GID is permitted. This check runs before the Unix socket/token is created.
- The unchanged single-operator service can retain its existing explicit run/research/export contract. **Do not reuse it as an adversarial multi-user boundary.**

## Verification and limits

Local nonroot Python regression: **72 PASS**, covering the tenant audit, operator service, Studio receipt handoff, and the new forbidden mixed-plan controls. Actual two-distinct-UID filesystem and Unix-socket rejection acceptance also **PASS** in an ephemeral Linux test; it does **not** test hostile kernels or Docker daemon tenant isolation. GitHub CI is the authoritative check for the reviewed branch head.

This is application-level *tool admission*, not kernel-enforced egress control. A malicious process under the same host UID could bypass the Python service and use the OS/network directly. No network namespace, restrictive mount namespace, seccomp profile, per-tenant rootless runtime or hostile-root isolation is deployed. The approved dedicated UID and bounded per-tenant cgroup are necessary but insufficient for strong multi-tenant security. A separate privileged operator must provision and attest a host sandbox; until then, multi-tenant public execution is **BLOCKED**.

No model can approve or start plans. No public HTTP or WebSocket execution bridge has been added. Do not merge or deploy PR #244 on this evidence alone; preserve `A_out <= A_in`.
