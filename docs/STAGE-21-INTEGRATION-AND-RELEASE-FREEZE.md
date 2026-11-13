# Stage 21 — exact-head integration evidence and safe release freeze

## Scope and verified design

Development PRs #129–#134 form a **dependent stack**, not independent main-branch patches: #129 fixes private workspace storage; #130 fixes execution admission; #131 adds source-grounded chat; #132 adds optional encrypted chat history; #133 adds opt-in read-only MCP apps; #134 adds Work Mode and encrypted local project persistence.

The Stage 21 read-only preflight makes this relationship executable. For every PR it fetches GitHub's current base/head branch and exact commit SHA, open/non-draft/mergeable state and all reported exact-head checks. It rejects wrong ancestry, stale/missing or duplicated checks, pending/skipped/failed checks, or unexpected branches. It checks six baseline jobs on each PR and the research-chat job for #131 onward. A second observation rejects main/head drift during collection. The new workflow triggers only for integration PRs targeting the Work Mode branch; it deliberately does not run on Work Mode PR #134 itself, avoiding a self-referential pending-check cycle. It separately verifies that Work Mode's cumulative head is an ancestor of the Stage 21 candidate.

Files:
- scripts/stage21-stack-preflight.py: live GitHub metadata or offline synthetic fixture; produces a bounded, non-secret JSON receipt.
- scripts/test-stage21-stack-preflight.py: 18 adversarial tests of failure and non-authority.
- .github/workflows/stage21-stack-integration.yml: runs the tests, verifies source ancestry and observed GitHub check results in read-only CI.

The only automatically supplied token is the ephemeral GitHub Actions token with contents/checks/pull-requests **read** permissions. No Railway/Render provider secrets, private recovery key, production file bytes, original workspace, or user data is read or written. This stage creates no new paid service or host.

## Interpretation and release freeze

A result named STACK_INTEGRATION_CHECKS_PASS__PRODUCTION_BLOCKED means that **development topology and previously reported exact-head GitHub checks passed at observation time**. It does not mean that a production service ran the new features, that a human used a phone, that external providers work, or that NEXUS has a generative LLM. The preflight observes test records, not the entire browser/HTTP suite itself. A report never grants merge, deployment or Seal authority, including when the checks pass.

The existing render.yaml defines an old Docker-backed Render service with autoDeployTrigger: checksPass. Main-branch merging might redeploy it. Do not promote any of these stacked branches to main merely for green CI: the actual original Railway /data full encrypted owner-held offsite backup and independently verified isolated restoration remain unproven. Track recovery under Issue #104, and actual authenticated first-human acceptance under Issue #70. Neither issue is closed by Stage 21.

Actual recovery requires owner-controlled valid provider access and an owner-held private decryption key; do not solicit or copy either into a public issue, PR, browser test or chat. The no-budget/no-personal-computer constraints remain.

## Self-critique

This integration gate is practical delivery-risk containment rather than a new public feature. Existing development features remain unpublished. Live GitHub metadata may become stale after a green run, so repeat the gate on an exact candidate close to any authorized promotion. Network failure, ambiguous mergeability or unexpected check statuses fail closed. This process is not an independent backup verification, a Rust release Seal, or evidence of real device/provider correctness.

Constitutional boundary: A_out <= A_in, and machine reports remain non-authoritative.
