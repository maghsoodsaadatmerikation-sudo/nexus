# Stage D — actual old-gateway downgrade on an isolated DATA COPY

## Goal

Validate the **behavioral risk of switching a newer NEXUS gateway to the historical Stage D restore binary** when both see the same types of files, without touching any real service, user record, key, or provider volume. This does **not** authorize a real downgrade or rollback.

The exact gateway source revisions are:
- old Railway restore: \`588dc7672146031425b16b34956876d644244ace\`;
- original Stage D source: \`9abbc067aad3ebbb0956432cf6682d2ea70e2824\`;
- later tested baseline: \`f4d027bb5f7e715b298f7cf7184fa621a2fb071d\`.

The \`NEXUS Historical Gateway Crash Restart Isolation\` GitHub Actions workflow builds all three **actual historical gateway executables** in temporary Git worktrees, using Rust 1.85.0, and runs both the earlier within-version restart fixture and the new \`scripts/test-stage-d-historical-copy-downgrade.py\` test. The latter runs for **both** newer source→older recovery→newer source and later baseline→older recovery→later baseline.

## Exact isolated procedure

For each newer gateway:
1. Run its real HTTP service with a **disposable API bearer token** and new \`NEXUS_DATA_DIR\` on \`127.0.0.1\`. Create only one synthetic workspace and one request; require workspace HTTP 201, request HTTP 202 and Pending status.
2. Kill the newer server, assert the exact \`requests/<hex-id>\` marker is \`pending\\n\`, and compute a bounded SHA-256 manifest of all source files.
3. \`shutil.copytree\` the entire synthetic source into a **new, different directory inode**. Verify file-by-file byte digest identity. All later old-version execution happens **only on this copy**, not the original.
4. Simulate a partially persisted request marker containing \`p\` in the copied data. Run the actual old recovery binary on the copy. The old gateway can read the existing workspace, but its in-memory request ledger returns 404 for both previously accepted and partial marker IDs. The old gateway accepts POST for each ID (HTTP 202), despite the newer on-disk markers. Kill the old process; the copied files have **not changed** from old request replay, so an on-disk differential alone cannot detect the already repeated acknowledgment.
5. Return the newer binary to the copied directory. It must restore Pending and Indeterminate, refuse both replayed IDs with 409 and preserve all copied marker bytes. The original synthetic source remains byte-for-byte identical to the pre-copy manifest.
6. Independently clone the original modern source to a **second** fresh copy. Create a synthetic \`.nexus-recovery-required\` quarantine marker. Verify the modern gateway returns 503 for new POST requests **and** workspace creations, and writes no data.
7. Stop the modern binary, run the real historical old recovery binary on that quarantined copy. The old binary must be identified as unsafe: it ignores the later quarantine marker, returns 202 for a new synthetic request and returns 201 for a **newly written synthetic workspace**. This writes only to the disposable copy. A bounded manifest must prove exactly the new workspace file was added, with no existing file or quarantine-marker changes.
8. Re-run the newer binary on this copy. It can read the old-written workspace but still refuses new POST work under the persisted quarantine. Again verify the original modern source was not modified.

A successful test is deliberately \`PASS_WITH_CONFIRMED_UNSAFE_LEGACY_DOWNGRADE\`. This means the unsafe behavior is **reproduced and recorded**, not that the rollback is safe. The emitted \`rollback_approved=false\`, \`production_release_authorized=false\` and \`release_gate=BLOCKED\` must not be interpreted as deployable status.

## Why the downgrade is unsafe

**Confirmed from the actual old executable:** it neither honors the durable newer request marker nor the newer recovery quarantine. On a cloned modern data tree it accepts request IDs that the modern version already marked Pending or Indeterminate. With a quarantine marker present it also accepts mutations the newer gateway refuses. A clean file-digest comparison can miss *logical replay*, because the old request code did not need to write its own marker. Reverse-migrating only the executable cannot repair the semantics of the persisted request log.

These observations require an explicit **versioned interoperability/rollback protocol** and a real isolated restore proof before any deployment or image switch. A previous historical Rust core fixture also found that the legacy reader accepts an empty-provenance event rejected by the later core. Neither issue is resolved by this test.

## Boundaries

- Only synthetic files and localhost HTTP; neither Railway nor Render is accessed by the test. No actual credentials, customer workspaces, real retained witnesses, costed volumes, production configuration, provider patches or deployed services are touched.
- The test uses actual Git historical source builds, **not verified bit-identical deployed provider images**. Provider runtime artifact attestation is still unproved.
- A SIGKILL/process restart after HTTP acceptance is not a real power-cut/hardware-disk failure or a destructive external-host recovery.
- Incompatible unknown future data fields, simultaneous writers, client retries, provider volume mounts and a complete schema reverse migration still need their own separate operator-approved tests.
- Never run a historical recovery binary against a live recent NEXUS data directory. Never interpret a successful old-version JSON read as safe write access.

PR stays stacked and Draft. No merge to the auto-deploying \`main\` branch until independent live-host evidence, backups, reviewed migration/revocation procedures, and production change approval exist.
