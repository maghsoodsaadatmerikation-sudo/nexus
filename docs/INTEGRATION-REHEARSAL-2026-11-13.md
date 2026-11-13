# NEXUS stacked merge rehearsal — 13 November 2026

## Why this exists
PR #129 currently reports mergeable=false against current main.
PRs #130–#134 depend in order on the original #129 source branch. A cumulative
stack can pass tests at its own historic head and still be incompatible with
main. PRs #153, #155 and #157 are separate deployment-held changes.

## Rehearsal scope
This branch introduces a no-release GitHub Actions witness that downloads only
Git refs into a disposable checkout and runs Git's native three-way
`merge-tree --write-tree --name-only -z` against immutable SHA references.
It captures only conflict **paths**, never conflicted contents or private data.
No merge commit, branch update, PR approval, main push, provider API request,
secret, credential, production volume or storage key is involved.

The statuses `CLEAN_MERGE_REHEARSAL_ONLY` and
`BLOCKED_BY_MERGE_CONFLICT` are diagnostic observations. Neither authorizes
main merging. A clean merge tree must still undergo compilation, signed review,
exact-head CI and independent recovery verification.

Read `integration-rehearsal.json` from the workflow artifact for the
conflicting files; next reconcile candidate code against actual main and run
full deterministic, Rust, browser and protocol gates on the *rebased* SHA.
Issue #104 remains the owner-held original-volume backup/restore blocker;
issue #154 remains the Render automatic deployment blocker; issue #156
tracks sleeping Railway admission and health-path mismatch.
