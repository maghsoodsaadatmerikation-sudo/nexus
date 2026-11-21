# Public Studio GitHub Actions startup failure: syntax remediation (2026-11-18)

## Observed failure

The `.github/workflows/studio-static-public.yml` workflow repeatedly
produced failed `push` runs with **zero jobs**, including workflow run
`44250980594`. The run displayed the workflow path in place of its
declared title and created no runnable steps. These failures say nothing
about browser, server, or live Render deployment acceptance.

## Exact source defect

The job-level `jobs.public-browser.if` contained an opening grouping
parenthesis without its matching closing parenthesis:

```text
... || (github.event_name == 'pull_request' && contains(..., '[verify-studio-public]')
```

The expression had **three '(' and two ')'** outside of quotes.
The corrected expression closes the final grouping parentheses:

```text
... || (github.event_name == 'pull_request' && contains(..., '[verify-studio-public]'))
```

This is a GitHub Actions expression syntax problem; it is not evidence
that Public Studio's public browser, PWA, audio, or model features failed.

## Implemented

1. Close the unmatched parenthesis without changing event permissions,
   source hashes, paths, provider calls, or browser logic.
2. Add `scripts/test-public-studio-workflow-expression.py` with deterministic
   regression checks of balanced delimiters and quoted literals, matching
   exact event gating, one job condition, and read-only permissions.
3. Run the regression suite from the existing unprivileged `pr-verify.yml`
   check alongside repository-wide workflow authority verification.

## Acceptance evidence still required

- Exact-head PR test suite: must pass.
- On a commit changing the workflow file, GitHub should register the
  named workflow and create jobs rather than produce an immediate zero-job
  validation failure. Because the fixed workflow's `push` trigger is limited
  to main and its `pull_request` trigger is path-filtered, **absence of a
  run** from a feature-branch push may be correct; do not infer success
  from absence alone.
- Review the public-witness unit job's real result from a matching PR trigger.
- Post-promotion live Chromium/WASM tests remain separately opt-in and are
  not asserted by the static expression fix.

## Scope and nonclaims

No existing privileged publishing workflow, deployment secret, release
tag, public provider, or user content has been changed. This is a stacked
draft PR, not an approved deployment. `A_out <= A_in`.
