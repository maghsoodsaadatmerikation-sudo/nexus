# NEXUS Studio build-template integrity (2026-11-19)

## Why this matters

Studio has reviewed editable sources in `web/`, a deterministic standalone HTML
bundle in `web/studio.html`, and a static/public installable package in
`public/studio/`. Two build stages used text substitution to assemble these.
An `assert` in the first stage can disappear when Python runs with `-O`; the
second stage previously performed unchecked `str.replace` operations. If a
template slot was renamed, deleted, or duplicated, the builder could silently
produce a valid-looking but incomplete package when not running the normal
stale-output check.

## Fix

Both stages now use `scripts/studio_template_contract.py`:

- `replace_exact` counts occurrences and raises `ValueError` if they differ
  from the declared count; the rule remains active under `python -O`.
- `build-studio.py` checks the complete, explicit set of module placeholders.
  Missing or unexpected `/*STUDIO_...*/` slots stop the build.
- `build-studio-static.py` checks all shell insertion points, preserving the
  two existing worker CSP occurrences, and checks every service worker
  integrity-template token.
- Only exact, reviewed slots can be replaced; the resulting bytes remain
  deterministic. Build-time exceptions do not write a new public package.

## Verification and negative tests

`scripts/test-studio-template-contract.py` exercises exact substitution,
missing and duplicated slots in the static shell, service worker marker
integrity, and a copied source tree under `python -O`. It also asserts that
the complete static shell bytes equal the checked-in public artifact. The
existing `--check` release gate continues to compare the exact packaged
artifacts. The regressions run in static acceptance and static release-candidate
CI workflows.

This is a **build-integrity improvement**, not a certificate of real browser
safety, production rollout, live model availability, or Stage D readiness.
