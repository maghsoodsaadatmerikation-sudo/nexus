# Phase 14 — operator-approved rootless namespace experiment

## Status: lab proof, not hosted tenant execution

A separate operator CLI (`scripts/nexus-rootless-probe.py`) runs a **reviewed,
exact SHA-256 pinned, private, static ELF** under the host user's unprivileged
UID, with an isolated **user / mount / network / PID / IPC / UTS namespace**.
It uses no Docker or host root and does not appear in the model tool registry,
Studio public UI, cloud API, plan schema, or tenant operator service.

The checked-in C fixture, `scripts/rootless-sandbox-probe.c`, demonstrates:

* PID 1 *inside* the new PID namespace; the host UID is unchanged.
* No `/etc/passwd`, `/proc`, `/home` or other host filesystem mounted.
* Operator workspace available **read-only** at `/workspace`; guest cannot
  create a workspace file. There is no automatic write-back to a project.
* The only other writeable filesystem is a 16 MiB private, noexec, nosuid,
  nodev `/tmp` tmpfs. No network interfaces are connected to the host netns.
* The guest executable is copied to an owner-only staging directory and the
  staging directory is bind-remounted read-only inside the new mount namespace.
* CPU, address space, file size, file descriptor and process-count RLIMITs are
  tightened before `execve`; output is SHA-256 summarized after a 64 KiB cap;
  the parent kills the entire new process group and PID namespace after timeout.
* On failure to establish the namespace or required mounts, result is
  `sandbox-failed`, **never** a PASS. The full plan must not be automatically
  retried; stdout and stderr bytes are not exported by the CLI.

## Reproducing the disposable test

Run this test as a **non-root** user on a Linux host where unprivileged
user namespaces and mount namespaces are enabled, with a working static C
compiler, `unshare`, and `mount`:

```sh
PYTHONPATH=nexus-cloud python -m pytest -q \
  nexus-cloud/tests/test_agent_rootless_probe.py
```

For manual use, first compile the **trusted** test fixture, prepare a 0700
operator-owned root with a workspace called `alpha`, a private executable and
`input.txt` with the literal `sentinel` in that workspace. Then:

```sh
sha256sum /absolute/private/probe
python scripts/nexus-rootless-probe.py \
  --root /absolute/private/operator-root --workspace alpha \
  --executable /absolute/private/probe \
  --sha256 EXACT_REVIEWED_SHA256 --approve-rootless
```

The CLI accepts arbitrary static ELF as a manually chosen operator proof only.
**Do not run untrusted binaries on production hosts on this basis.**
Static ELF parsing is a bounded header policy; it is not a malware scanner or
full executable attestation. Kernel vulnerabilities, hostile same-UID
processes, inherited host socket FDs (the harness closes them), host cgroup
limits, disk-quota enforcement, genuine tenant independence, writable project
storage, portable architectures, and privileged host compromise remain outside
this lab proof. In particular the experiment does **not** integrate with the
production tenant service or re-enable its deliberately denied `run` tool.

The real GitHub Actions `rootless-namespace` job is a strict acceptance gate.
If the hosted runner disables unprivileged user namespaces, it fails rather
than pretending an isolated guest ran. The existing PR remains **Draft**.
