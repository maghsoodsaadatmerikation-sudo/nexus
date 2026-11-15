# Stage D — execute actual historical gateway binaries with synthetic crash/restart data

## Purpose and exact scope

This stage tests **the original Axum HTTP gateway executable** from three exact Git revisions in separate temporary filesystem roots, using synthetic request and workspace data only:

| Role | Git revision | Previously observed Railway deployment |
|---|---|---|
| Old recovery | \`588dc7672146031425b16b34956876d644244ace\` | \`nexus-stage-d-restore\` (SLEEPING) |
| Original Stage D source | \`9abbc067aad3ebbb0956432cf6682d2ea70e2824\` | \`nexus-stage-d\` (SLEEPING) |
| Later baseline reference | \`f4d027bb5f7e715b298f7cf7184fa621a2fb071d\` | repository \`main\` at prior inspection, **not asserted deployed** |

The new dedicated \`.github/workflows/stage-d-historical-gateway-restart.yml\` workflow fetches exact Git history with **no persisted checkout credentials**, creates detached disposable worktrees and compiles the actual \`artifact-05\` gateway binary for each exact revision with Rust 1.85.0. It copies the compiled binaries to a private temporary directory. The Python driver \`scripts/test-stage-d-historical-gateway-restart.py\` then starts each binary bound exclusively to \`127.0.0.1\` with a per-run ephemeral API token, dedicated synthetic \`NEXUS_DATA_DIR\` and no user or production credentials.

The test deliberately uses \`SIGKILL\` only **after an authenticated HTTP 202 response**. This is an abrupt **process termination**, not a simulated power outage during a journal fsync, and the test must never be called a real destructive hardware/host backup drill.

## What the tests check

1. Requests are denied without a bearer token (401); a synthetic workspace can be created (201); synthetic request submission returns 202 and is queryable as pending before the process exits.
2. A real gateway process is forcibly killed and restarted over the **same disposable directory**. The synthetic workspace is fetched again to verify local persistence across process restart.
3. The historical old recovery revision is expected to **lose in-memory request status on process exit**: GET for a previously accepted synthetic request becomes 404 and reposting the same request ID returns 202. This is a **known legacy replay/idempotency weakness** discovered by executing that actual binary; the regression **requires** reporting it, rather than falsely certifying the old version safe.
4. Newer original Stage D and later baseline revisions must reopen their durable \`requests/<hex-id>\` marker, return the existing pending status after restart, and refuse the duplicate request with 409.
5. For newer revisions only, a synthetic **one-byte \`p\` reservation** is inserted into the disposable \`requests/\` directory (not a real live volume). Reopening must classify it as **indeterminate**, preserve the bytes and refuse its request ID as a replay. This tests interrupted reservation recovery without attempting a nondeterministic kill at a live request's commit boundary.
6. For newer revisions only, a synthetic \`.nexus-recovery-required\` file is inserted into a disposable data directory. Restart must latch quarantine and reject any POST request with 503, without creating a new request marker.

A passing result is deliberately \`PASS_WITH_KNOWN_LEGACY_REPLAY_RISK\`, and always includes \`production_release_authorized=false\` and \`release_gate=BLOCKED\`. If a newer binary allows duplicate requests or loses the synthetic marker, CI fails.

## Security, operational and epistemic limits

- No Railway or Render service is started, modified or contacted. No production filesystem, user data, service secret, signer key, provider patch or chargeable volume is accessed.
- The runner executes only loopback HTTP against the three binaries it compiled locally. The test does not prove no outbound traffic is possible at OS level; no outside API endpoints or connector credentials are supplied.
- Exact source commits are checked before compilation. The binaries are **not** proven bit-for-bit identical to the historical images that Railway previously ran. Provider-native current/runtime provenance is still missing.
- Observing deterministic process-exit behavior is not power-loss durability or host failure-domain independence. No actual failed disk, destructive real restore, cross-host transport, encrypted offsite backup or reverse data migration is simulated.
- The older gateway does not contain the later durable request-ledger contract. Running it on a real newer persistent volume might enable replay or unsafe state interpretation. **Never** downgrade it automatically.
- The tests do not validate production load, authentication policy beyond the isolated test, database schema migration, simultaneous writers, simultaneous host crashes or exact live rollout integrity.
- Every test uses a **fresh private directory** and disposable token, and child processes are killed by their isolated process group before moving to the next historical version. Temporary worktrees and data roots are deleted on completion or failure.
- The historical Rust workspace reader's separate known issue remains: the oldest core accepted an event with empty provenance. This new gateway test does not repair old deployed binaries.

Review \`STAGE-D-DATA-ROLLBACK-COMPAT.md\` and the independent-host release gate before designing any real executable migration. A real rollback remains BLOCKED until independently approved off-host backup/checkpoint, current image attestation, old/new data-schema compatibility and isolated destructive restore are proven.
