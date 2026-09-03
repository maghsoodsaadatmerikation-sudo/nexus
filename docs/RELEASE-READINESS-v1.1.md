# NEXUS v1.1 Release Readiness Gate

This gate prevents a `v1.1.0` release from being treated as ready until Stage D durable-host evidence exists, contains the required lifecycle sequence, and is internally consistent.

It does not create a tag, publish a release, provision infrastructure, or claim durable production by itself.

## Constitutional boundary

The gate evaluates operational release evidence only. It does not authorize, interpret, rank, or promote machine output into human judgment. The invariant remains:

`A_out <= A_in`

## Command

```bash
bash scripts/v1.1-release-readiness.sh ./stage-d-evidence <40-character-deployed-commit>
```

PASS requires all of the following:

- HTTPS/auth preflight evidence showing public liveness and exact 401 rejection for missing and wrong bearer credentials;
- complete capture evidence bound to the exact deployed 40-character repository commit;
- a sanitized replacement lifecycle event bound to that same commit before survival verification;
- a post-replacement snapshot JSON-equivalent to the captured snapshot;
- a separate destructive lifecycle event and an observed authenticated HTTP 404 `workspace_not_found` result before any restore;
- a post-restore snapshot JSON-equivalent to the captured snapshot;
- the captured snapshot hash to match `before.sha256` and every snapshot-bearing phase result;
- all required phase results to be `Status: PASS`, `Token Recorded: NO`, and `Authority Expansion: NONE`;
- lifecycle identifiers and timestamps to pass the restricted format checks;
- no credential-like material in result or lifecycle evidence files.

The script prints `V1.1 RELEASE READINESS: PASS` only when all checks pass. Otherwise it exits non-zero. Missing evidence is reported with `V1.1 RELEASE READINESS: BLOCKED`; malformed content may also terminate the gate non-zero before a PASS can be emitted.

## Evidence hierarchy

The readiness gate intentionally distinguishes observed behavior from operator/provider corroboration. A replacement event identifier cannot substitute for the survival fetch, and a destructive event identifier cannot substitute for the observed 404 absence proof. Both lifecycle sequence and observed network state are required.

## Fail-closed rule

CI verifies both sides of the gate:

1. an incomplete Stage D evidence pack must be rejected; and
2. a synthetic structurally complete lifecycle-bound pack must pass, after which removal or corruption of key lifecycle evidence must make the gate fail again.

Passing ordinary CI does not simulate or substitute for Stage D external-host evidence. The synthetic fixture validates gate logic only.

A release remains blocked until Stage D is complete on a real persistent host and the exact deployed commit also has a successful `NEXUS Verification` run that is independently checked.

## Evidence hygiene

The release-readiness gate must never require or record the bearer token. It operates only on already-created evidence files. A PASS from this gate is an operational release-readiness statement, not an epistemic correctness claim.
