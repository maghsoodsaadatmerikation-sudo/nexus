# Stage D — executable synthetic startup admission guard

## Why this step matters

Exact historical gateway tests in PR #237 proved that the old recovery revision \`588dc7672146031425b16b34956876d644244ace\` can read some newer workspace JSON, yet **ignores durable request reservations and the modern recovery quarantine**. Running that older revision with a newer data volume can re-accept previously committed, ambiguous or quarantined work. A passing schema-number check is therefore not a safe rollback gate.

\`scripts/workspace-stage-d-startup-guard.py\` adds a **new, executable pre-start barrier** for a future governed launch chain. It refuses the known unsafe legacy revision **even if a caller creates a correctly hashed policy naming the old binary**. It accepts only the two separately tested newer historical revisions \`9abbc067aad3ebbb0956432cf6682d2ea70e2824\` and \`f4d027bb5f7e715b298f7cf7184fa621a2fb071d\` in a **synthetic-only test scope**. Any future revision must be explicitly reviewed and added by code change, not dynamically self-authorized.

### Admission criteria

The operator supplies a strict canonical 0600 policy and its separately approved exact-byte SHA-256, plus an exact binary SHA-256, the approved 40-character Git SHA, a private data directory and a historical ELF gateway binary.

The policy has exactly these fields:

\`\`\`json
{
  "schema": "nexus.stage-d.guarded-start.v1",
  "approved_git_sha": "9abbc067aad3ebbb0956432cf6682d2ea70e2824",
  "approved_binary_sha256": "64_lowercase_hex_of_approved_exact_elf",
  "data_layout": "nexus.durable-requests.v1",
  "execution_scope": "synthetic-only",
  "required_quarantine_support": true,
  "production_release_authorized": false
}
\`\`\`

The example SHA placeholder is **not** a real SHA value: replace it with the exact cryptographic digest of the **reviewed** ELF and separately pin the policy SHA; never derive both independent reference pins at verification time from an untrusted candidate.

Admission performs:

1. Strict/unique policy JSON validation; separately pinned exact policy bytes; exact approved revision; **hard-coded deny** for the vulnerable historical recovery Git SHA; exact binary SHA across a privately owned, nonlinked ELF FD. Additional policy fields and production-authorizing claims are rejected.
2. POSIX exclusive lock on the actual data-directory inode. All files must be private operator-owned regular files, without symlinks/hardlinks, under bounded entry and total-byte budgets. Workspace filenames must be the UTF-8 hex encoding of their IDs and snapshots must pass the existing NEXUS v1 event/provenance structural screen. Unknown file formats, schema versions and malformed event histories fail closed.
3. Durable request-marker directory must be private; each marker name must be recognized lowercase hex. Only the tested marker forms \`pending\\n\` and \`p\` are admitted by the initial guard. Unknown or tampered marker bytes force review, not automatic retry.
4. A nonempty \`.nexus-recovery-required\` marker is **permitted only with a known quarantine-enforcing modern binary**, and remains intact. The modern HTTP gateway itself must return 503 on state-changing actions while quarantined.
5. \`inspect\` does not execute any binary and outputs a bounded JSON report with \`release_gate=BLOCKED\`, \`production_release_authorized=false\`.
6. \`run-synthetic\` additionally requires an IPv4 \`127.0.0.1:PORT\` binding and a disposable \`NEXUS_API_TOKEN\`. On supported Linux/POSIX platforms it calls \`os.execve(binary_file_descriptor,...)\` on the **same inode already hashed**, rather than reopening a replaceable pathname. The held data-directory lock FD is inherited across the exec and remains held for the lifetime of the actual gateway process.

The executable boot path is tested in CI against actual historical Rust/Axum binaries. The first run detected that historical Rust request markers may be created with permissive default filesystem modes. The guard **refuses** such modes, and CI narrows file/directory permissions **only on its disposable synthetic copy** before confirming the guarded restart. In the current candidate source, `artifact-05/src/request_store.rs` now creates NEW request directories in mode 0700 and NEW marker files in mode 0600, with a Rust unit regression. The source change does not alter existing deployed files or automatically chmod existing folders; they require a separate operator-owned migration/inspection. It **does not edit historical binaries, their deployed image entrypoints, or Railway startup configuration**. A legacy executable invoked **without this guard** remains vulnerable; no code-level wrapper can retroactively stop direct execution of an already deployed old binary. This is a narrow, explicit start-of-process barrier—not a full replacement for runtime process sandboxing, host compromise protection or an active request protocol.

## Synthetic invocation

Create a *fresh private disposable root* with controlled workspace and reservation files. Build a reviewed modern gateway binary and keep its exact SHA/commit pinned separately. Then:

\`\`\`sh
python3 scripts/workspace-stage-d-startup-guard.py inspect \
  --binary /private-test/nexus-gateway \
  --binary-sha256 PIN_APPROVED_ELF_SHA256 \
  --runtime-git-sha 9abbc067aad3ebbb0956432cf6682d2ea70e2824 \
  --data-dir /private-test/nexus-synthetic-data \
  --policy /private-test/approved-start-policy.json \
  --policy-sha256 PIN_APPROVED_POLICY_SHA256
\`\`\`

To execute the checked binary **only in synthetic isolation**, use the same flags with \`run-synthetic\` and these environment variables:

\`\`\`sh
NEXUS_BIND_ADDR=127.0.0.1:13000 \
NEXUS_API_TOKEN=EPHEMERAL_TEST_BEARER \
python3 scripts/workspace-stage-d-startup-guard.py run-synthetic \
  --binary /private-test/nexus-gateway \
  --binary-sha256 PIN_APPROVED_ELF_SHA256 \
  --runtime-git-sha 9abbc067aad3ebbb0956432cf6682d2ea70e2824 \
  --data-dir /private-test/nexus-synthetic-data \
  --policy /private-test/approved-start-policy.json \
  --policy-sha256 PIN_APPROVED_POLICY_SHA256
\`\`\`

This example is **not** a supported Railway launch configuration and must not be used to auto-deploy. It explicitly forbids any production approval. The guard and current CI use Python 3 on Ubuntu; the Docker runtime image has **not** been updated to include the Python guard or a pinned launch policy.

## Tests and release limitations

The existing heavy historical gateway GitHub workflow builds exact old/source/target Rust binaries and runs \`scripts/test-workspace-stage-d-startup-guard.py\`. It must demonstrate:
- old recovery binary refused with correct matching, separately hashed policy;
- source and target inspected/started through the FD-based guard on private synthetic data, actual authenticated HTTP request submission and replay refusal, and recovery quarantine blocking HTTP writes;
- wrong hash, unknown revision, attempt to authorize production, disabled quarantine safety, malformed/tampered data or permissions, symlink/hardlink policy/marker paths, and malformed executables refused;
- root locks and original synthetic files kept private; no Railway/Render or production data accessed.

Even a green CI does **not** show that a deployment cannot bypass the guard: deployment must **make the guard the immutable entrypoint**, prove it is actually executed in the released image, pin the complete image digest/approved Git revision and preserve independently custodied checkpoints and backups. The existing source/restore Railway services remain sleeping and on differing revisions. Do not merge into auto-deploying \`main\` or silently reconfigure those services as part of this step.

**Next operational step:** package and independently attest an immutable candidate image whose only entrypoint is this guarded startup, then run a separately authorized off-host destructive recovery on a NEW disposable volume with external witness checkpoint. That requires a non-synthetic implementation, explicit human-reviewed budget, separate custody and release approval; none are claimed here.
