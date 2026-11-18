# NEXUS integration merge-readiness audit — 2026-11-18

## Observed GitHub facts

- Integrated PR: **#288**, draft, open, head `c55b89c73f0ee4cc2d097490a18a95a543881796`, base `main`.
- All six distinct exact-head workflows in the last integrated PR run completed **successfully**.
- The repository has an **active repository ruleset** (ID `20870033`, “Merikation”), targeting its default branch and enforcing required check `readonly-verification` with GitHub Actions integration ID `15368`.
- The legacy branch-protection endpoint is not accessible to the GitHub App. Its limited branch metadata showed `required_status_checks.enforcement_level=off`—this does **not** override or negate the separate, active ruleset. Earlier statements treating this as no required check were incomplete.
- The current ruleset API response reports `bypass_actors=[]`. The audit now **rejects any bypass actor or missing bypass metadata** rather than treating the mere existence of a required check as unconditional enforcement.
- That active ruleset requires **zero approving reviews** and sets `strict_required_status_checks_policy=false`. Thus an independent review is not required by GitHub and a freshly updated base is not required by that rule.
- No release-publishing workflow has been modified and historical attestation proof does not authorize current release.

## Implemented

`scripts/merge-readiness-audit.py` is an **offline, read-only snapshot parser** with exact-sha and repository-ID pinning. It validates:

1. Repository identity, live default branch SHA, PR #288 head/base binding, same-repository PR provenance.
2. Active ruleset ID, exact default-branch coverage, required GitHub Actions `readonly-verification` check, ruleset review and strict status options.
3. The six expected workflow names **and exact paths**, successful complete first-attempt PR run metadata, source/head repository IDs, PR association and exact candidate SHA.
4. Failures and missing runs as `NOT_PROVEN`. A prior successful run with a later failed matching run cannot mask the failure.
5. A human-readable blocker report: `DRAFT_PR`, non-strict base freshness, no independent required approval, not-all-CI-proven and need for an explicit owner merge decision. Output ALWAYS sets `merge_authorized=false` and `release_authorized=false`.

`scripts/test-merge-readiness-audit.py` includes hostile synthetic cases for stale/forged workflow metadata, forked runs, wrong PR association, reruns, duplicate JSON keys, disabled ruleset, changed GitHub App integration and malformed source metadata. The tests run in the usual read-only PR verification workflow.

`.github/workflows/merge-readiness-audit.yml` makes a **separate read-only public metadata** observation of the integrated PR #288 and active ruleset, with `contents/actions/pull-requests:read`, no persistent checkout credentials, no publisher/deploy access, and no write scopes. The job's success means *the snapshot report was generated without malformed metadata*; it must not be read as authorization or readiness to merge.

## Remaining human decision points

- Independent review of all 23 changed files in #288.
- Owner choice to consolidate in #288 or merge the original stacked PRs, **never both**.
- If stronger enforcement is desired, update the GitHub ruleset using owner/admin UI to require independent approving review and/or strict base freshness; this code does not alter repository policy.
- Decide separately whether historical read-only preflight should ever become a mandatory part of a privileged publication workflow.
- Live Public Studio browser and actual production deployment remain unverified by this review.

**No main merge, release, tags or hosting changes.**
