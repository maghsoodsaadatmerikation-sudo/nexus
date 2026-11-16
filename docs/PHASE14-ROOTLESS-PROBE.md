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

## Phase 15 — fail-closed kernel hardening and host capability distinction

The bootstrap now finishes its trusted mounts and chroot **before** irreversibly
removing all effective, permitted and inheritable Linux capabilities. Locked
`SECBIT_NOROOT` and `SECBIT_NO_SETUID_FIXUP` prevent the nested UID 0 from
reacquiring root capabilities at `execve`; `PR_SET_NO_NEW_PRIVS` is mandatory.
A seccomp BPF program explicitly checks native `AUDIT_ARCH`, kills mismatched
architectures and x86 x32 ABI calls, and returns EPERM for clone/fork, new
namespaces, mount/remount, pivot/chroot, ptrace, BPF and similar high-risk
syscalls. An unrecognized CPU architecture or failed filter installation
prevents any guest launch. This remains a **bounded lab proof**, not a safe
universal executable sandbox or a substitute for a dedicated host/VM.

The static ELF probe refuses to return PASS unless it observes: zero guest
capability sets, `NoNewPrivs=1`, seccomp filter mode, a denied `unshare` call,
and a denied workspace remount. The executable's ancestors are opened through
`O_NOFOLLOW` dirfds, requiring private paths except root-owned sticky `/tmp`.
Workspace source integrity and file/time/output boundaries are unchanged.

GitHub-hosted Ubuntu runners can prohibit *unprivileged* user namespaces by
a global AppArmor restriction. Generic CI runs still execute static/negative
contract tests and mark real OS acceptance **SKIPPED** when unavailable.
A separate, mandatory `rootless-namespace` job temporarily configures the
**disposable CI runner only** for the required rootless userns test and
restores its previous sysctl setting on exit; tests themselves still run as a
non-root user. If the host cannot be configured or the namespace cannot be
established, that dedicated job fails, and the PR cannot be promoted. No
production host setting is changed, and this is not independent security
attestation. In a real operator host, the admin must choose and maintain an
appropriate security policy; there is no automatic sysctl alteration.
