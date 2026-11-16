# NEXUS phase 12: Linux tenant separation — a fail-closed host gate

**Status: development / operator acceptance only. Not production multi-tenancy.**

This stage adds an **opt-in** strict Linux operator entrypoint, a **read-only**
host audit, and a disposable **actual cross-UID** regression. It does not add
any HTTP endpoint, hosted automation, browser/LLM execution ability, Linux
account provisioning, privilege escalation or public deployment.

## Threat model and supported boundaries

- An installation administrator must provide a *different* non-root Linux UID
  **and primary GID** for every tenant, private mode-0700 workspace root and
  a dedicated v2 cgroup. The service does **not** switch UID or create users.
- Per-UID cgroup **leaf** must be named `nexus-tenant-<UID>` or
  `nexus-tenant-<UID>.scope`; memory.max must be finite **64–512 MiB**,
  pids.max finite **8–128**, and cpu.max finite **at most 2 CPUs**.
  Shared, unlimited, malformed or nested cgroups cause failure, not fallback.
- On strict startup the process lowers RLIMIT_NOFILE to <=256,
  RLIMIT_FSIZE to <=32 MiB, disables core dumps, sets umask 077 and enables
  Linux `PR_SET_NO_NEW_PRIVS`, then verifies its UID/GID/capabilities.
- The existing Unix control socket is still inside each private root (0600),
  together with a private single-link token (0600); SO_PEERCRED requires the
  actual connecting UID and manual execution approval remains required.
- **Critical limitation:** a shared/rootful Docker daemon (including membership
  in the `docker` group) can defeat host UID separation. The strict tenant
  service **disallows every `run` step** at admission. A separately assessed,
  per-tenant rootless execution backend would be required before enabling
  container execution. The older local **single-operator** CLI remains separate
  and has not magically become multi-tenant secure.
- File operations remain constrained to the operator account and its private
  workspace. Strict tenant mode now forbids **run, package, and research**
  execution: package accepts an arbitrary absolute export target, and research
  contacts an external metadata service, neither of which belongs in a
  network/egress-unattested shared tenant environment. Inert review may show
  those tool types, but **start rejects the entire plan before journal claim**.
  Allowed steps are only read/write/edit/verify_sha256/search/preview_edit.
- The dedicated tenant GID must not be accompanied by **any** unrelated
  supplementary group (not only root group 0). In particular, inherited
  docker/lxd/disk groups can invalidate UID-only isolation. The tenant daemon
  refuses to start before socket creation when getgroups() contains another GID.

## Start and audit, after independent host provisioning

Run the following under **the dedicated non-root tenant identity** in an
operator terminal, *not* as root, not from a web request, not from a model:

```sh
python3 scripts/nexus-tenant-service.py --root /private/uid-specific-root
```

This command refuses to bind its socket or mint a token if UID/GID/cgroup
preconditions are missing. The independent host auditor requires read-only
root visibility to inspect two or more *existing* tenant services; it **never
starts them** or connects as a client:

```sh
sudo python3 scripts/nexus-tenant-host-audit.py \
  --tenant /private/tenant-one:PID_ONE \
  --tenant /private/tenant-two:PID_TWO
```

The audit ties a process to a live listening Unix socket FD, verifies all
four UID/GID fields, effective capabilities 0, NoNewPrivs=1, private
socket/token/roots, distinct UID/GID/root/cgroup, disjoint path ancestry,
finite CPU/memory/PID limits, and absence of unsafe ancestor permissions.
It emits only account numeric IDs and bounds, never file contents, capability
tokens, plan paths or source code. Its `production_attested` value is **false**;
it is a point-in-time gate vulnerable to a hostile root/admin, kernel attack,
mount namespace changes and time-of-check/time-of-use races. An actual hosted
security audit remains necessary.

## CI acceptance (no public host changes)

- Pure Python tests exercise invalid quotas, unlimited resources, root/UID
  identity, insecure ancestors, symlink escapes, missing peer socket ownership,
  duplicate tenant identifiers and rejection of `run` under strict policy.
- The **tenant-os-boundary** GitHub job uses `sudo` **only** in a disposable
  Ubuntu runner to spawn two *temporary numeric unprivileged UIDs*. It does not
  add persistent host accounts, connect to Docker or host a public service.
- The two tenants each prepare and execute an approved file-writing plan with
  the same workspace name but distinct output contents. Direct cross-UID file
  reads and cross-UID operator client attempts must be rejected. Unprovisioned
  strict multi-tenant startup must fail closed.
- Existing Engineering Agent contract tests and isolated real Docker tests
  remain independent. Docker's success in a single-operator runtime is **not**
  evidence of a safe shared-tenant container host.

### Explicit non-goals

No authenticated public API, no model-driven execution, no automatic sudo,
no per-user rootless Docker provisioning, no cgroup creation or manipulation,
no hardware Android testing, no throughput benchmark, no adversarial kernel
isolation attestation and no production multi-tenant deployment.

Keep PR #244 in Draft until all CI checks and separate infrastructure/operator
security acceptance have been reviewed. In particular, `A_out <= A_in` still
applies: the assistant can suggest steps but does not manufacture approval.
