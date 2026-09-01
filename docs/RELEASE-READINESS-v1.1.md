# NEXUS v1.1 Release Readiness Gate

This gate prevents a `v1.1.0` release from being treated as ready until Stage D durable-host evidence exists and is internally consistent.

It does not create a tag, publish a release, provision infrastructure, or claim durable production by itself.

## Constitutional boundary

The gate evaluates operational release evidence only. It does not authorize, interpret, rank, or promote machine output into human judgment. The invariant remains:

`A_out <= A_in`

## Command

```bash
bash scripts/v1.1-release-readiness.sh ./stage-d-evidence <40-character-deployed-commit>
```

PASS requires:

- complete Stage D capture, survival, and restore evidence files;
- the captured snapshot hash to match `before.sha256`;
- post-replacement and post-restore snapshots to be JSON-equivalent to the captured snapshot;
- every Stage D phase result to be `Status: PASS`;
- every result to state `Token Recorded: NO`;
- no credential-like material in phase result files;
- the evidence pack to be bound to the exact deployed 40-character repository commit.

The script prints `V1.1 RELEASE READINESS: PASS` only when all of these checks pass. Otherwise it exits non-zero and prints `V1.1 RELEASE READINESS: BLOCKED`.

## Fail-closed rule

CI deliberately verifies that the release-readiness gate refuses an absent or incomplete Stage D evidence pack. Passing ordinary CI does not simulate or substitute for Stage D external-host evidence.

A release remains blocked until Stage D is complete on a real persistent host and the exact deployed commit also has a successful NEXUS Verification run.

## Evidence hygiene

The release-readiness gate must never require or record the bearer token. It operates only on already-created evidence files. A PASS from this gate is an operational release-readiness statement, not an epistemic correctness claim.
