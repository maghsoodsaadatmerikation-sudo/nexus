# Stage D Durable-Host Evidence Protocol

This protocol turns the remaining v1.1 durable-production requirement into a repeatable evidence procedure. It does not itself prove that any external host is durable.

## Constitutional scope

Stage D evaluates operational persistence and recovery only. It does not authorize, interpret, rank, or convert machine output into human judgment. The invariant remains:

`A_out <= A_in`

A health check, successful restart, or successful restore is never evidence of epistemic correctness.

## Evidence harness

Use `scripts/stage-d-evidence.sh` from an operator machine. The evidence directory must be kept independently of the host under test.

Required environment:

```text
NEXUS_BASE_URL=https://<durable-host>
NEXUS_API_TOKEN=<operator-held secret>
```

The token is used for authenticated requests but is never written to the evidence files.

## Phase 1 — Capture

Choose an existing authenticated workspace that can act as the persistence witness and bind the evidence to the exact repository commit actually deployed:

```bash
export NEXUS_WORKSPACE_ID=<workspace-id>
export NEXUS_DEPLOYED_COMMIT=<40-character-deployed-commit>
bash scripts/stage-d-evidence.sh capture ./stage-d-evidence
```

Expected evidence:

- `before.json`
- `before.sha256`
- `workspace-id.txt`
- `deployed-commit.txt`
- `result-capture.txt` with `Status: PASS`

The snapshot must remain outside the host being tested. `NEXUS_DEPLOYED_COMMIT` must identify the exact code revision running on the host; the later v1.1 release-readiness gate refuses evidence bound to a different commit.

## Phase 2 — Real replacement and survival verification

Replace or recreate the service/container in the actual hosting environment while preserving only the host's declared persistent storage. Do not restore the backup before this check.

Then run:

```bash
bash scripts/stage-d-evidence.sh verify-survival ./stage-d-evidence
```

PASS requires the authenticated workspace fetched after replacement to be JSON-equivalent to the independently stored pre-replacement snapshot.

Expected additional evidence:

- `after-survival.json`
- `result-survival.txt` with `Status: PASS`

A restart that does not actually replace the service/container is insufficient for the Stage D replacement claim.

## Phase 3 — Destructive recovery verification

After survival has been proven separately, perform the documented destructive recovery exercise on the host: remove the test workspace's durable backing state or provision a clean durable instance, without destroying the independent backup.

Confirm the workspace is absent, then run:

```bash
bash scripts/stage-d-evidence.sh restore-verify ./stage-d-evidence
```

PASS requires server-side import/revalidation to succeed and the restored snapshot to be JSON-equivalent to `before.json`.

Expected additional evidence:

- `after-restore.json`
- `result-restore.txt` with `Status: PASS`

## Stage D completion criterion

Stage D may move to `COMPLETE / VERIFIED` only when all of the following are true on a real external host:

1. HTTPS endpoint is active.
2. Application port remains non-public behind the HTTPS boundary.
3. Persistent storage is mounted for `NEXUS_DATA_DIR`.
4. `capture` passes before replacement and records the exact deployed repository commit.
5. A real service/container replacement occurs.
6. `verify-survival` passes without using restore first.
7. A separate destructive recovery exercise is performed.
8. `restore-verify` passes.
9. Bearer authentication remains fail-closed.
10. The exact deployed repository commit has a successful NEXUS Verification run.
11. `scripts/v1.1-release-readiness.sh` validates the complete Stage D evidence pack against that exact commit.

Until all eleven conditions are evidenced, the deployment must not be called durable production and `v1.1.0` must not be sealed.

## Evidence hygiene

Do not commit API tokens, authorization headers, private deployment credentials, or user evidence payloads. The Stage D result files intentionally record only operational PASS state, snapshot hashes, and the fact that no token was recorded.
