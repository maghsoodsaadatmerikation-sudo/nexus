# Continuation context verification — 2026-11-26

Candidate parent: `e95a13302e11dc3750302df3b8b2dd9d46c7e99d` (PR #508).

Added `scripts/test-studio-followup-browser.py` to the Studio workflow. Its
synthetic context-API matrix covers nine English/Persian continuation commands,
all four independent source/related-chat opt-in combinations, original message
preservation, active versus hidden branches, model-only text, explicit topic
changes, truncated history, fresh threads, isolation and project immutability.
It uses the existing disposable narrow/wide Chromium harness. It does not test
composer controls, provider answer quality or a deployed installation.

Local verification:

- All 51 commands in the workflow's initial deterministic/source-test step passed
  in native Python/Node (including 133 core checks).
- `build-studio.py --check` and `build-studio-static.py --check` passed.
- New matrix: 224 assertions passed under native Node VM with actual WebCrypto,
  TextEncoder and TextDecoder. The executed core source was confirmed to occur
  verbatim in `public/studio/index.html`. Only the test's load event and result
  element were simulated. This is not a browser pass.
- Python compilation and `git diff --check` passed.
- Real Chromium attempt failed before page startup: `/usr/bin/chromium` points
  to an installation whose `/usr/lib/chromium/chromium` binary is missing.
  Exact-head CI must execute the new browser matrix before accepting it.

No live provider evaluation, merge, deployment or release claim.
