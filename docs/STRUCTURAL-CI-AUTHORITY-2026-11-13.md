# Structural CI authority repair — 13 November 2026

Status: **proposed, not deployed**. This repair does not grant release authority.

## Confirmed structural findings

1. `scripts/scripts/verify_test_matrix.py` was a historical placeholder that emitted `TEST-MATRIX: PASS` unconditionally. Its entrypoint now delegates to the real `scripts/verify_test_matrix.py` preflight, preserving error codes.
2. The workflow-authority guard previously inspected only `id-token`, `attestations` and `contents` write scopes on PR workflows. Other token scopes such as `actions`, `packages`, `deployments` and `pages` could be overlooked. It also used assertions, which disappear under optimized Python.
3. Unknown/inline permission syntax and workflows using `*.yaml` were not safely covered. Ordinary PR workflows now require an explicit, minimal root `contents: read` map, and all job-level permission maps are checked. Unrecognized event/permission layouts fail closed.

## Evidence and scope

- Ten adversarial local Python tests passed (including `python -O`, alternate suffixes, broad write scopes, PR target, ambiguous declarations and job-level elevation).
- The PR verification workflow now runs these tests and runs the previously misleading nested preflight entrypoint.
- The protected attest/publish workflows retain their existing main-only authority checks and are not edited.
- This is not a general YAML interpreter. The gate deliberately requires the existing documented two-space event keys and simple, block-style permissions. Any future new syntax needs explicit, reviewed parser support.
- Local tests exercised synthetic workflow fixtures. **Repository-wide hosted CI and exact candidate gate results must be observed after the PR is opened.** No live volume, secret, release, provider configuration or production deployment is changed.
