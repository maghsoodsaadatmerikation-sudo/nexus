# Phase 27 — installed-operator real-process restart acceptance

**Status:** draft PR #244; nonroot Linux/Python 3.13 disposable acceptance only.
No production deployment, outside-host survival claim, Docker execution, model
automation or publisher signature is authorized by this check.

## Operational question

The installed operator can create a durable single-use plan receipt. Earlier
tests covered the private socket roundtrip and preservation of an interrupted
claim after a crashed process. They did not require one complete, independently
restarted installed-service cycle that recovers its finished journal receipt
without re-running the same approved plan.

## Acceptance procedure

The new scripts/test-operator-restart-pilot.py is an **explicitly approved,
standalone CI witness**. It uses the installed operator ZIP already created
and manifest-verified by the NEXUS Operator Pilot Distribution workflow. It is
*not* shipped as an executable tool in the operator installation.

The script rejects root users, non-Linux platforms, Python below 3.13, missing
explicit --approve-disposable and incorrect installed-manifest SHA-256. It
creates only a private disposable workspace and outbox and uses the same
two-step synthetic plan for all runs:

1. Verify a fixed synthetic input file's SHA-256, then write a fixed result.
2. Start a real **separate OS process** running the installed private
   Unix-socket service. Inspect the inert review before submitting the plan.
3. Wait for the terminal journal receipt, verify finished state, both steps,
   and the resulting fixed file.
4. Kill the server OS process with SIGKILL to simulate an unexpected daemon
   death. Do not touch the completed approval journal.
5. Require explicit acknowledgment for stale transport revocation and reject
   implicit recovery. Recovery does not claim to identify or stop orphaned
   jobs on a real external host.
6. Start a new installed-service process on the same disposable root. Verify
   the credential rotated, original finished receipt is still available,
   the **same digest cannot be re-executed**, and output/journal are unchanged.
7. Stop the new process gracefully; verify its transport files are removed.
   Destroy the disposable root and verify installed files remain unchanged.

Example operator-only acceptance (use verified private installation and an
out-of-band SHA pin for that *exact* installed manifest):

~~~bash
python -I -B scripts/test-operator-restart-pilot.py \
  --installed "$HOME/nexus-pilot-installs/candidate" \
  --expected-manifest-sha256 YOUR_TRUSTED_MANIFEST_SHA256 \
  --approve-disposable
~~~

The GitHub operator-distribution.yml workflow invokes it after deterministic
bundle creation, digest-gated installation and basic installed smoke, then
re-runs installed manifest verification. Every subprocess executes on an
ephemeral nonroot Ubuntu runner. The output is a bounded synthetic JSON verdict
without private tokens or source text.

## Evidence classification / non-claims

- **Proves if CI passes:** two distinct real server process lifetimes on an
  ephemeral runner; the finished local journal survives daemon SIGKILL;
  explicit operator-controlled transport revocation; new credential;
  read-only recovery of the existing result; denial of replay of the same
  approved digest; no installed-file mutations in the test.
- **Does not prove:** survival across power loss or machine reboot, host
  disk/fsync guarantees, external backups, real Docker orphan cleanup,
  provider credentials, multi-tenant service isolation, malicious same-UID
  process resistance, signed publisher identity, public HTTPS deployment
  or an autonomous tool-using model.
- This is a recovery **acceptance test**, not permission to auto-resume
  interrupted work. An unfinished started journal remains quarantined.
- Before promotion to a real durable host, require a separate operator-approved
  isolated host trial with independent evidence, live workload survival,
  non-destructive restart, storage restoration and explicit orphan review.

Keep PR draft and never promote until exact-head CI and separate host
security review pass. Preserve NEXUS authority invariant A_out <= A_in.
