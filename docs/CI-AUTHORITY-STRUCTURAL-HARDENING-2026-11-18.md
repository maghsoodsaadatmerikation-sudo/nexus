# CI authority boundary — structural hardening (2026-11-18)

## Why

The original `verify-workflow-authority.py` selected only two PR workflows
for most read-only checks and used substring/regex checks for privilege names.
That could miss alternate legal YAML shapes, job-level permissions or future
PR-triggered workflows. `assert` checks also vanish under `python -O`.

## Enforced invariants

1. Every `.github/workflows/*.yml` and `*.yaml` must declare a literal,
   explicit top-level `on:`, `permissions:` and `jobs:` block mapping.
   Ambiguous forms, duplicate keys, anchors and unsupported security syntax
   are rejected instead of guessed.
2. For a workflow triggered by an untrusted event (PR, merge queue, issue,
   discussion, review or reusable call), the global token must explicitly
   include `contents: read`, never a write permission.
3. Each individual job is also checked for permission overrides. An untrusted
   workflow cannot gain write access through a job-level `permissions` block.
4. `pull_request_target` is prohibited; adding it cannot silently turn
   untrusted code into privileged base-repository execution.
5. Existing named attestation workflows retain their explicit push-to-`main`
   restrictions and require literal publication scopes. Other existing release
   workflows remain out of scope and are **not** newly authorized.
6. All checks use exceptions rather than Python `assert`, preserving
   enforcement with optimizations enabled.

## Test and integration

- `python3 scripts/test-workflow-authority.py`: synthetic read-only and
  adversarial fixtures for escalation, inline YAML, duplicates and job override.
- `python3 scripts/verify-workflow-authority.py`: repository-wide policy gate.
- Both run inside `NEXUS PR Verification` with `contents: read` and no
  deployment, secrets, tags, release writes or API calls.

## Boundaries and review requirements

This is a deliberately narrow **static grammar validator**, not a general
YAML parser and not a security boundary against repository collaborators who
can edit both code and CI. It does not prove runner isolation, third-party
action safety, release-workflow `workflow_run` provenance, deployment health
or human-independent witness evidence. Syntax outside the accepted literal
subset requires explicit parser review, not a silent bypass.

The change is proposed in a separate branch/PR, not deployed, and should stay
unmerged until the exact-head GitHub Actions result is inspected. Existing
constitutional constraint remains `A_out <= A_in`.
