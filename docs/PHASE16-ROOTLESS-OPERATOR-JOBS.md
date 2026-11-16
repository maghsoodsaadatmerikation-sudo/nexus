# Phase 16 — private rootless operator jobs (draft / not deployed)

## Trust boundary

This is a **manual operator-local** workflow, not an autonomous model tool.
No TCP, HTTP, web UI bridge, public API, user-supplied browser command, or
multi-tenant shared executor is added. The existing tenant service starts its
`OperatorServer` with container execution disabled and **cannot enable** rootless
jobs. The ordinary operator service also **defaults** to rootless jobs disabled.
A dedicated operator opts in at daemon launch, and must independently review
and supply the exact job plan digest for each run. `A_out <= A_in`.

A job plan binds: the current immutable workspace manifest SHA-256; the
owner-only static ELF's SHA-256 and absolute path; literal arguments, bounded
timeout, workspace identity, and a fresh 128-bit random nonce. JSON is strictly
canonical and rejects duplicate keys. The plan is written to a private owner-
controlled outbox outside every workspace. Changing any field produces a
different plan SHA-256, which requires separate approval.

An authenticated owner-only Unix socket with SO_PEERCRED and a 256-bit local
token admits the job. On `probe-start`, **before** launching any process, the
service verifies the plan and executable and fsyncs a single-use journal claim.
The worker verifies the executable and workspace state again. A crash leaves
`started` and blocks replay. Files are mounted read-only, the guest cannot
access the host network, Linux capabilities are dropped, seccomp rules apply,
and timeout/output/cancellation kill the entire process group. No guest stdout,
stderr, path or arguments are copied into a shareable receipt. Stopping is a
request and must be followed by an inspected terminal receipt; no rollback is
promised. An interrupted/unfinished journal is **not** evidence of success.

## Operator-only example

Create a private 0700 root with workspace `alpha`, a separate 0700 outbox,
and compile the reviewed static proof fixture using `cc -static`. Place the
private executable in a separate 0700 directory, mode 0500. Compute its exact
SHA-256. Then, in a terminal dedicated to the operator:

```sh
python scripts/nexus-operator-service.py serve \
  --root /absolute/private/root --enable-rootless-probe
```

Prepare the plan in a second private terminal (no execution yet):

```sh
python scripts/nexus-rootless-job.py prepare \
  --root /absolute/private/root --workspace alpha \
  --executable /absolute/private/bin/probe --sha256 REVIEWED_ELF_SHA256 \
  --out /absolute/private/outbox
```

**Inspect the entire private JSON plan** at the printed location and verify
its manifest, executable SHA, arguments, timeout and nonce. Copy the **exact**
printed plan digest into separate human-controlled commands:

```sh
python scripts/nexus-rootless-job.py review \
  --root /absolute/private/root --workspace alpha \
  --digest REVIEWED_JOB_PLAN_SHA256 --plan /absolute/private/outbox/nexus-plan-PREFIX.json
python scripts/nexus-rootless-job.py start \
  --root /absolute/private/root --workspace alpha \
  --digest REVIEWED_JOB_PLAN_SHA256 --plan /absolute/private/outbox/nexus-plan-PREFIX.json
python scripts/nexus-rootless-job.py status \
  --root /absolute/private/root --workspace alpha --digest REVIEWED_JOB_PLAN_SHA256
python scripts/nexus-rootless-job.py stop \
  --root /absolute/private/root --workspace alpha --digest REVIEWED_JOB_PLAN_SHA256
```

Never infer `complete` from a start/stop acknowledgment. Status receipts use
`nexus.rootless.operator-receipt.v1`, are deliberately separate from existing
Studio v3 planning receipts, and carry no execution authority. There is no
model-controlled callback or automatic import into Studio.

## Acceptance and limitations

Unit contract tests cover plan tampering, stale workspace, modified ELF,
operator opt-in, denial in tenant mode, authenticated cancellation, durable
one-use journal claims and redacted receipts. A dedicated *real Linux* CI job
also exercises the end-to-end rootless guest and a stop/kill flow in disposable
Ubuntu. When the host refuses user namespaces, the job fails or skips according
to explicit host gating; simulated tests do not certify OS isolation.

This is **not** a production security attestation, multi-tenant offering,
remote execution service, safe general code interpreter, or guaranteed defense
against hostile same-UID processes, malicious Linux kernel behavior, privileged
host administrators or host cgroup misconfiguration. PR remains Draft and may
not be promoted based solely on these tests.
