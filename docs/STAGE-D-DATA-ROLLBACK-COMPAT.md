# Stage D — bounded, read-only data downgrade compatibility screen

## Observation: workspace schema does not prove an old reader will work

The NEXUS historical deployed Stage D revisions examined were:
- recovery \`588dc7672146031425b16b34956876d644244ace\`;
- source \`9abbc067aad3ebbb0956432cf6682d2ea70e2824\`;
- later main reference \`f4d027bb5f7e715b298f7cf7184fa621a2fb071d\`.

GitHub showed **139 commits from recovery to source** and **40 from source to that main reference**. The workspace Rust struct's \`schema_version\` remains **1** in both inspected historic versions, but the later service has introduced a request reservation ledger and complete-data snapshot/restore behavior not present as the same files in the older recovery revision. The current full-data backup is \`nexus.data-snapshot.v1\`: it captures hex-encoded workspace \`*.json\` files, \`requests/<hex-id>\` reservation marker bytes and the optional \`.nexus-recovery-required\` quarantine marker.

**Consequence:** matching workspace \`schema_version=1\` or a common Git ancestor proves neither backward deserialization nor safe data rollback. A new service may write state an older service cannot interpret, and downgrading code does not undo committed data or already-accepted requests.

## Implementation

\`scripts/workspace-stage-d-data-rollback-screen.py\` provides two read-only commands: \`inspect\` and \`rollback-gate\`.

Both consume **two actual NEXUS v1-format, complete-data snapshot archives** (historical baseline and proposed after/rehearsal dataset), an operator-approved Stage D rehearsal plan and **separately retained exact SHA-256 pins for all three**. The files are opened without following symlinks, are size-bounded, must have unique linked identities, unambiguous canonical JSON and valid per-record content hashes, sizes and canonical base64. Workspace file names must equal the UTF-8 hex-encoded workspace IDs; only workspace \`schema_version=1\` is structurally recognized.

The tool checks:
- workspace files missing, newly introduced or changed;
- invalid audit creation events, unsupported kinds, wrong/missing provenance and non-contiguous sequence numbers;
- audit history shortened, diverged or extended beyond the prior snapshot;
- changed workspace state, including unknown added/removed fields;
- new or disappeared request reservation markers and changes in their actual bytes, including \`indeterminate → pending\` (possible replay of uncertain work) or \`pending → indeterminate\`;
- removal or addition of the recovery quarantine marker;
- operator plan authorizing any real volume write, live deploy, destructive test, signing-key rotation, provider patch application, or omission of independent backup and explicit schema compatibility review.

It outputs only **aggregate counts and generic finding codes**, never user content, workspace IDs or original request markers.

Two outcomes are intentionally narrow: \`NO_CONTENT_DELTA_ONLY\` (identical decoded files, not necessarily same archive provenance) and \`DOWNGRADE_REVIEW_REQUIRED\` (any changed files). If an archive is corrupted or structurally unsupported, inspection exits nonzero. Even for identical contents, \`automatic_data_rollback_authorized=false\`, \`production_release_authorized=false\`, \`release_gate=BLOCKED\` and \`old_rust_reader_executed=false\` remain unconditional. \`rollback-gate\` **always exits nonzero**, including for a fully identical archive.

### Offline invocation

Generate snapshots with the repo's existing \`scripts/data-snapshot.py\` **only after quiescing all writers**, on separately authorized offline or isolated data directories. Do not export or copy a live mounted production volume in this stage. Independent operators must retain artifact bytes and their exact hashes outside the failure domain.

\`\`\`sh
python3 scripts/workspace-stage-d-data-rollback-screen.py inspect \
  --before /private-review/before-data-snapshot-v1.json \
  --before-sha256 PIN_BEFORE_ARCHIVE \
  --after /private-review/after-data-snapshot-v1.json \
  --after-sha256 PIN_AFTER_ARCHIVE \
  --plan /private-review/stage-d-nonexecuting-upgrade-plan.json \
  --plan-sha256 PIN_INDEPENDENT_REHEARSAL_PLAN \
  --source-commit APPROVED_FULL_SOURCE_GIT_SHA \
  --restore-commit APPROVED_FULL_RECOVERY_GIT_SHA \
  --target-commit APPROVED_FULL_REHEARSAL_TARGET_SHA
\`\`\`

The plan must use the exact prior \`nexus.stage-d.nonexecuting-upgrade-rehearsal.v1\` schema and must explicitly forbid live writes and deploys. The separately supplied three full commits must match its pin, and both fallback revisions must correspond exactly to the actual pre-rehearsal source/recovery code revisions.

Run the same command with \`rollback-gate\` rather than \`inspect\` only as a **fail-closed blocking gate**. Do not interpret an \`inspect\` exit zero as authorization.

## What must be tested next, independently

The screen is a **structural, offline differential** using the production snapshot encoder. It does **not execute either historical Rust binary** and does not revalidate the full Rust constitutional audit semantics. Such semantic verification must be done by the actual version-pinned Rust readers in separate, disposable isolated containers on synthetic and externally approved (non-sensitive) snapshots, before any executable old/new compatibility claim. Git ancestry and JSON parsing cannot substitute for this.

A legitimate future operator-controlled, safely quarantined real drill must also prove:
1. Explicit versioned manifest of request marker conventions, state/quarantine semantics and supported workspace/event variants for **both exact builds**.
2. Actual historical readers can parse, load and read back snapshots from the new version without corrupting state; rejected inputs cause zero writes.
3. A copy-on-write reverse migration, if necessary, is itself versioned, provenance-pinned, idempotent and tested under crashes and restart using disposable volumes; irreversible loss or unknown variants must halt.
4. Independent encrypted off-host backup, external monotonic checkpoint custody, two-host provider evidence and complete release review.

**Never downgrade a live writer by changing only the Git commit**. In particular, request markers of uncertain execution must not be reclassified as accepted or retried, and the absence of a marker after restoration is not proof of original execution state.

## CI / test coverage

\`scripts/test-workspace-stage-d-data-rollback-screen.py\` uses **only synthetic records** and invokes \`data-snapshot.backup\` to produce true v1 archive format. It tests identical snapshots, missing/new workspaces, appended/invalid histories, request additions/removals/uncertainty transitions, quarantine retention, altered schema, invalid archive envelopes/base64/checksums, symlinks/hardlinks, pinned plan version mismatches and forbidden deployment/rollback settings. CI checks the exact commit without Railway, GitHub or application credentials.

No server was awakened, no production disk read or modified, no new paid resource created, no signer key changed, no merge to main and no live rollback attempted.
