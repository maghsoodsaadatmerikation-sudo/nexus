# Protected main merge-freshness gate — 13 November 2026

## Observed control gap

The live GitHub ruleset \`20870033\` protecting NEXUS's default branch
\`main\` was read through GitHub on 13 November 2026. It is active, requires
a PR and the \`readonly-verification\` status from GitHub Actions, forbids
deletion and force pushes, and has no bypass actors. However, its
\`strict_required_status_checks_policy\` is **false**. A successful status
check may therefore have been evaluated against an older base commit.

The read-only GitHub connector can inspect this setting but cannot change
repository rulesets. This remains a real administrator action, not something
that a source-code PR can claim to repair.

## Added defense in depth

\`scripts/verify-pr-merge-freshness.py\` fetches the current \`main\` head and
the fixed official ruleset with the read-only \`gh api\` client in a PR job.
It rejects:

- base SHA different from the currently observed main head;
- unprotected or excluded main, inactive/wrong ruleset, or **visible** bypass actors;
- missing/ambiguous required GitHub Actions check identity;
- disabled \`strict_required_status_checks_policy\`;
- malformed/unavailable/oversized GitHub responses.

The step runs before costly Rust/Docker verification, to avoid marking an
obsolete candidate as release-ready. It is **not** a production deployment
gate, does not grant any release authority, and does not access Render.

GitHub's documented API redacts `bypass_actors` for read-only tokens. The
CI guard reports `bypass_actor_visibility=redacted_not_verified` instead of
inventing a no-bypass claim; if the field is visible and non-empty, it
rejects it. An operator with ruleset write permission must independently
check for bypass actors. No elevated token is passed to untrusted PR code.

The 16 adversarial tests are entirely synthetic, do not contact GitHub and
include \`python -O\`, checked SHA, ruleset and JSON mutation cases.

## Mandatory GitHub action (still outstanding)

In repository **Settings → Rules → Rulesets → Merikation** (ruleset
\`20870033\`), enable **Require branches to be up to date before merging**
under required status checks. Keep \`readonly-verification\` required,
GitHub Actions as its integration, PR-required, no force push, no branch
deletion and no bypass actors. Then independently re-read the ruleset API
and verify \`strict_required_status_checks_policy: true\`.

Until that real change occurs, the new CI guard is **expected to fail
closed**, not to emit a misleading green status. A PR merge must not be
attempted by bypassing or weakening the guard.

## Scope and residual risks

The GitHub-enforced strict rule is the authoritative merge-time protection;
the explicit comparison of event base SHA to the live tip is defense in depth
and can race with a later branch update. It does not replace the strict
Ruleset setting. GitHub's required-check enforcement also depends on current
workflow/ruleset settings, which must be re-read. A single-maintainer
repository with no independent review remains exposed to malicious changes
in verification code; this change does not claim to solve that entire
trusted-maintainer boundary.

This is deliberately separate from the Render auto-deploy/backup blocker
(issue #154), Draft PR #166 and Stage D independent production restoration.
No GitHub ruleset mutation, provider configuration, secrets, volume data,
release tags, or deployments were changed by this source update.
