# Structural repair integration rehearsal — 13 November 2026

**Engineering only.** This is a read-only integration candidate, not a release
candidate, deployment authorization or a production restore witness.

## Immutable source inputs

- PR #165: `20ecab7e62ee68c2db0af381d05f4593c7bec99e`
- PR #166: `65f05db948adab355d068b63e1ee029980b5efba`
- PR #167: `18ccfca038574afc178fb1d69baaca9c4262b50f`
- PR #169: `bb438c6d07abc023f6fe72321dee0b3c4f63f16a`
- Base main: `560badfa977f6ed1e1298388ee1ce3650ebc9daa`

The combined tree reuses the exact Git blob for each non-overlapping changed
path in those four proposed PRs, including original file modes. Exactly one
shared path, `.github/workflows/pr-verify.yml`, is combined manually:
both the workflow-authority regression/preflight checks from #165 and the
live strict-ruleset/base-freshness guard from #167 must remain.

This composition does **not** rewrite the original source PRs or alter main,
release tags, production volume, provider settings, secrets or user data.
It does not establish that the original branches can be merged independently
in any order. All four individual PRs remain under their existing holds.

## Read-only cross-repair execution

`.github/workflows/structural-integration-rehearsal.yml` exercises the
actual Rust/Docker/HTTP read-only verification harness, adversarial suites
for all four repairs, durable data/quarantine and ENOSPC contract, the
workflow authority guard and the manual Render Blueprint validator.
It uses `contents: read` and a checkout with persistent credentials disabled.
It cannot read Render volumes or disable live automatic deployment.

The ordinary `readonly-verification` job of the PR verification workflow
must **still fail closed** while repository ruleset 20870033 has
`strict_required_status_checks_policy=false` (issue #168).
A successful `independent-integration` engineering check would not satisfy
the mandatory merge gate, change GitHub ruleset enforcement or provide
permission to deploy.

## Conditions before promotion

1. Verify the **live** actual production-linked Render service has auto-deploy
   disabled, and inspect provider revision and recoverability (issue #154).
2. Enable strict up-to-date required status checks in the actual GitHub
   ruleset and review bypass actors with authorized readback (issue #168).
3. Re-run the exact final composite candidate with verified CI.
4. Review the combined workflow authority, manual render contract,
   full-data restore and single-workspace transfer boundaries.
5. Obtain explicit production promotion approval separately. Do not infer
   permission from a successful rehearsal or move historical seals.

Until then this candidate must remain **Draft / Unmerged**.
