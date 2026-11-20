# Phase 47 — NEXUS Studio public acceptance after a separately authorized Render promotion

## Why this exists

At the time of the original Phase 47 design, the source-only Studio package was green but the public site served older HTML, service-worker and device-control files. The historical pre-promotion drift described below no longer represents the current provider state. Before one is attempted, the existing `studio-static-public.yml` acceptance had two structural problems: it inherited the older Pilot 12 observer's **300,000-byte cap**, below the current reviewed Studio HTML size, and it had a **5-minute job timeout** even though the model's own real-weight load and offline generation can legitimately take longer.

## Post-deployment read-only witness — 19 November 2026

The connected Render workspace `tea-dabhioe10ojc73acbs8g` confirms the **existing**
static service `srv-dbrjurc9v7es73cqe0v0` has a new **live** deploy,
`dep-dbvkuonf3r2c73cj3930`, from Git commit
`9e05b840fc2d36d7bc268aede2693ab4d6fb08e3`. The previous successful
live deploy was `dep-dbvgqotg1s2s73f6ghtg`, source
`e4f24218d7a3882391b593d78641d7a5ff50866d`. AutoDeploy remains disabled.

The owner's continuation was approved in chat; this document change is
**read-only verification only**, not additional deployment authorization.
The separate prior-live source fallback witness for the previous build
passed on nine public HTTPS assets and retained a source-only ZIP and its SHA
sidecar in GitHub Actions run `44597628585`. **That does not independently
confirm Render's retained rollback build artifact.**

The GitHub PR titled `[verify-studio-public]` triggers an independent
public-origin test against exactly the same `public/studio/` assets.
The document is the only source change in that PR: a PASS confirms bytes,
separate browser sessions and opt-in local model execution **only when the
public-browser job itself succeeds**. Its source branch has a different commit
ID because of the documentation change; the tested public asset bytes are
otherwise the ones from the deployed Git commit above. The provider deploy
ID must still be verified in Render independently.

## Changes

- `scripts/verify-studio-public.py` now sets a **485,000-byte cap shared with the Studio release package**. The observer self-test accepts the current generated Studio HTML and rejects an exact-match response one byte above the shared bound.
- `studio-static-public.yml` has a fast read-only unit/source job and a separate **22-minute post-promotion acceptance** job. On an ordinary PR it runs source/unit checks but **does not** interrogate or claim the public website was promoted. Full public checks require a manually dispatched run or the existing explicit `[verify-studio-public]` marker.
- Manual dispatch requires the **exact 40-character Git source commit** expected to have been deployed. It blocks when that input disagrees with the checked-out commit; neither the input nor green CI grants deploy authority.
- Public acceptance first fetches nine exact fixed-origin HTTPS assets and decoded icon pixels. If any source remains stale or unreachable it fails before browser/model testing.
- Two separately launched fresh-profile Chromium sessions then each test **true browser-network-offline app reload**, explicit encrypted vault reopen, code-only cache, preservation of private data during cache removal and rejection of a corrupted offline shell. Both outputs must agree on their reviewed check list and exact public source digest.
- One separate real Chromium model acceptance downloads the pinned, consent-gated WASM weights and verifies actual model generation using an explicitly supplied synthetic fact while the browser network is disabled, input size rejection, cancellation, and limited cache erase. It is **not** a hosted frontier-model claim.
- `verify-studio-public-acceptance.py` refuses missing/stale source identity, unreviewed public paths, either red/mismatched browser result, unsigned/offline-unproven browser report, model revision/runtime mismatch, and simulated model success. Its final `studio-public-acceptance.json` omits generated answer text and forces `actual_render_deploy_id_verified:false`, `real_android_hardware_verified:false`, `owner_promotion_authorized:false`, `production_seal:false` and `authority:none`.

## How to use it after an approved Render promotion

1. **First confirm the intended Render workspace/service**. The repository's historical service ID is `srv-dbrjurc9v7es73cqe0v0`, URL `https://nexus-studio-merikation.onrender.com/`. Verify its current source branch, build command, publish path, latest live deployment and an independently restorable previous deploy. Do not infer any of these from old documents.
2. Obtain the owner's explicit authorization for that exact Render service and target commit. The Stage 46 ZIP is review-only; the correct published directory contains only `public/studio` assets and no private keys or model cache. Leave the original Railway Stage D service and volume untouched.
3. After a successful authorized deploy, dispatch [NEXUS Public Studio Witness](https://github.com/maghsoodsaadatmerikation-sudo/nexus/actions/workflows/studio-static-public.yml) on the newly deployed `main`, entering the exact source SHA in `expected_source_commit`.
4. Require the read-only source/unit job and the public-browser job to PASS. Inspect `studio-public-assets.json`, `studio-public-browser-first.json`, `studio-public-browser-second.json`, `studio-public-model.json` and the summarized `studio-public-acceptance.json`. Do not claim success from a skipped public job or from the local-only release candidate.
5. Independently record the **actual** Render deploy ID and source commit from the provider, and test a real user's Android browser/archive separately without sending private credentials or content into the reports. A successful browser run is not production availability, owner hardware validation, server backup/restore or a Stage D seal.

## Self-critique and rollback

- This workflow is **read only** and does not have the Render provider's exact deployment identity. Source-byte matching and actual public browser tests do not replace that provider record.
- Executions use disposable Chromium profiles. They test new-user encrypted archive creation/reopen, but they cannot guarantee migration of an existing user's encrypted browser vault. Never erase browser storage or private backups to force a passing test.
- Temporary network/third-party weight download failures fail closed rather than becoming synthetic PASS. They may not indicate defective public HTML, so retain stage-specific evidence for diagnosis.
- Running both browser tests against the exact public origin prevents a single lucky cache activation from being promoted into a broad claim, but two passing runs still do not prove every Android device and software version.
- Preserve independently verified rollback deploy details before release. If any public check fails, halt promotion claims and restore the **verified previous deployment** through authorized Render controls; compare the restored origin's public assets and browser behavior. The historical initial November deploy is **not** automatically an accessible rollback snapshot.
- Both PR and workflow keep `permissions: contents: read`, no provider token, no action that triggers deployment and no claim of user authorization. The earlier Pilot 12 Issue #260 is separate. `A_out <= A_in`.
