# Stage D Durable-Host Evidence Protocol

This protocol turns the remaining v1.1 durable-production requirement into a repeatable, fail-closed evidence procedure. It does not itself prove that any external host is durable.

## Constitutional scope

Stage D evaluates operational transport security, persistence, replacement survival, destructive absence, and recovery only. It does not authorize, interpret, rank, or convert machine output into human judgment. The invariant remains:

`A_out <= A_in`

A health check, successful replacement, or successful restore is never evidence of epistemic correctness.

## Evidence harness

Use `scripts/stage-d-evidence.sh` from an operator machine. The evidence directory must be kept independently of the host under test.

Network phases require:

```text
NEXUS_BASE_URL=https://<durable-host>
NEXUS_API_TOKEN=<operator-held secret>
```

The token is used for authenticated requests but is never written to evidence files.

## Phase 0 — HTTPS/auth preflight

Before creating the persistence witness evidence, prove that the public endpoint is HTTPS, liveness succeeds, and protected workspace routes fail closed for both a missing bearer and an intentionally wrong bearer:

```bash
bash scripts/stage-d-evidence.sh preflight ./stage-d-evidence
```

Expected evidence:

- `result-preflight.txt`
- `Status: PASS`
- `Endpoint Scheme: HTTPS`
- missing and wrong bearer rejection PASS markers
- `Token Recorded: NO`

No capture may proceed without this preflight PASS.

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

After the provider reports the replacement live, record a sanitized lifecycle marker. Use the provider deploy/replacement identifier when one exists; otherwise use an operator identifier that can be independently correlated with provider logs. Do not put credentials into the identifier.

```bash
export NEXUS_REPLACEMENT_EVENT_ID=<provider-or-operator-event-id>
export NEXUS_REPLACEMENT_AT_UTC=<YYYY-MM-DDTHH:MM:SSZ>
export NEXUS_REPLACEMENT_COMMIT="$NEXUS_DEPLOYED_COMMIT"
bash scripts/stage-d-evidence.sh record-replacement ./stage-d-evidence
```

Then, without restoring anything, prove the workspace survived:

```bash
bash scripts/stage-d-evidence.sh verify-survival ./stage-d-evidence
```

PASS requires the authenticated workspace fetched after replacement to be JSON-equivalent to the independently stored pre-replacement snapshot.

Expected additional evidence:

- `replacement-event.txt`
- `after-survival.json`
- `result-survival.txt` with `Status: PASS`

A process restart that does not actually replace the service/container is insufficient. `verify-survival` refuses to run without a recorded replacement event bound to the captured deployed commit.

## Phase 3 — Destructive absence proof

After survival has been proven separately, perform the documented destructive recovery exercise on the host: remove the test workspace's durable backing state or provision a clean durable instance, without destroying the independent backup.

Then record the destructive action while proving, over the authenticated API, that the witness is actually absent:

```bash
export NEXUS_DESTRUCTIVE_EVENT_ID=<provider-or-operator-event-id>
export NEXUS_DESTRUCTIVE_AT_UTC=<YYYY-MM-DDTHH:MM:SSZ>
bash scripts/stage-d-evidence.sh verify-absence ./stage-d-evidence
```

PASS requires the authenticated witness lookup to return exactly HTTP `404` with `{"error":"workspace_not_found"}`. This creates:

- `absence-response.json`
- `destructive-event.txt`
- `result-absence.txt` with `Status: PASS`

This phase prevents a restore operation from being counted as destructive-recovery evidence when no destructive absence was ever observed.

## Phase 4 — Restore verification

Only after destructive absence PASS, restore from the independently held snapshot:

```bash
bash scripts/stage-d-evidence.sh restore-verify ./stage-d-evidence
```

PASS requires server-side import/revalidation to succeed and the restored snapshot to be JSON-equivalent to `before.json`.

Expected additional evidence:

- `after-restore.json`
- `result-restore.txt` with `Status: PASS`

`restore-verify` refuses to run unless the destructive absence result and lifecycle marker exist.

## Stage D completion criterion

Stage D may move to `COMPLETE / VERIFIED` only when all of the following are true on a real external host:

1. Public HTTPS endpoint is active and preflight is PASS.
2. Missing and wrong bearer credentials are rejected by a protected workspace route.
3. Application port remains non-public behind the HTTPS boundary.
4. Persistent storage is mounted for `NEXUS_DATA_DIR`.
5. `capture` passes and records the exact deployed repository commit.
6. A real service/container replacement occurs and is represented by a sanitized lifecycle event tied to that same commit.
7. `verify-survival` passes without restore first.
8. A separate destructive recovery exercise is performed.
9. `verify-absence` observes the witness as HTTP 404 before any restore.
10. `restore-verify` passes after the destructive absence proof.
11. The exact deployed repository commit has a successful NEXUS Verification run.
12. `scripts/v1.1-release-readiness.sh` validates the complete Stage D evidence pack against that exact commit.

Until all twelve conditions are evidenced, the deployment must not be called durable production and `v1.1.0` must not be sealed.

## Evidence hierarchy

The evidence pack intentionally distinguishes three kinds of proof:

- **observed network evidence** — HTTPS/auth behavior, survival fetch, absence 404, restored fetch;
- **content-integrity evidence** — exact commit, workspace identity, snapshot hash, JSON equivalence;
- **lifecycle corroboration** — provider/operator replacement and destructive-action identifiers plus UTC timestamps.

Lifecycle identifiers are corroborating evidence. They never substitute for the observed network checks.

## Evidence hygiene

Do not commit API tokens, authorization headers, private deployment credentials, SSH keys, or secret environment values. The Stage D result/event files intentionally record only operational PASS state, sanitized lifecycle identifiers, UTC timestamps, snapshot hashes, and the fact that no token was recorded.
