# Phase 46 — NEXUS Studio public static promotion preflight and rollback boundary

## Purpose

Turn the current reviewed Studio from a GitHub-only/local-phone release into a **source-bound, inspectable public release candidate** before any authorized promotion of the existing Render static service. This stage creates a public-only immutable ZIP, an independent SHA-256 manifest, a real local Chromium acceptance record and a **read-only observation** of the presently deployed public assets. It **does not deploy or restart any service**.

### Current known boundaries (source documentation)

- Public origin: `https://nexus-studio-merikation.onrender.com/`.
- Render static Studio service recorded in the repository: `srv-dbrjurc9v7es73cqe0v0`.
- Historical initial deployment: `dep-dbrjurk9v7es73cqe1a0`, source `ba81a44a8150098c636481ec32922ef7e2d93124`. This is a **historical reference**, **not a verified currently usable restore point**.
- Render AutoDeploy for the public Studio was documented as **OFF**. The current service's configuration, latest deployment and permission to promote must be confirmed from the intended workspace immediately before any deployment.
- The original Railway Stage D `/data` volume is a **different** protected service. It must remain untouched and its production recovery gate remains independent.
- The phone-only `/device-check.html` self-check remains in the **localhost** distribution. It is **not included** in the public Render site candidate because it explicitly checks a `127.0.0.1` origin. Shipping it publicly would produce a misleading BLOCKED status.

## How the candidate is constructed

The read-only [`NEXUS Studio Static Source Release Candidate`](https://github.com/maghsoodsaadatmerikation-sudo/nexus/actions/workflows/studio-static-source-release.yml) workflow checks out the exact source commit with no stored credentials; runs `scripts/build-studio-static.py --check`; executes negative ZIP/source/authority tests and a true local Chromium offline/encrypted-session lifecycle; and publishes seven artifact files:

1. `nexus-studio-static-site.zip` — exactly 13 public, source-reviewed assets, under `nexus-studio-static-site/`, **no private vault, project, key, provider token, hosted model, APK or runtime data**.
2. `nexus-studio-static-site.zip.sha256` — independent CI sidecar to compare against the downloaded ZIP.
3. `nexus-studio-release-manifest.json` — commit pin, SHA-256 and length for every public asset, ZIP digest and explicit `REVIEW_CANDIDATE_ONLY`/`authority:none` release flags.
4. `nexus-studio-release-local-browser.json` — local synthetic real-Chromium/verified offline-code lifecycle; **not an Android hardware test and not a public release test**.
5. `nexus-studio-public-before-promotion.json` — legacy fixed-origin read-only comparison of nine key public assets (HTML, service worker, manifest, both icons and four device-control modules) with statuses `SOURCE_MATCH_ONLY`, `PUBLIC_SOURCE_DRIFT`, or `INCOMPLETE_PUBLIC_OBSERVATION`.
6. `nexus-studio-public-all-assets.json` — new **complete fixed-origin HTTPS observation of all 17 source-reviewed files**, including the PDF modules, worker and licenses that the nine-file witness previously omitted. It verifies the exact candidate ZIP and manifest before the first request, keeps strict per-file byte and MIME bounds, compares seven+ nonimage resources byte-exactly, allows only identical decoded RGBA icon pixels when Render reencodes PNGs, never follows redirects and records each path as `MATCH`, `PIXEL_MATCH`, `DRIFT` or `UNREACHABLE`. All statuses are read-only evidence, not deploy authorization.

7. `nexus-studio-release-decision-hold.json` — **source-locked release-decision report** for the current 17-file observation. It verifies the complete candidate ZIP, manifest, source commit and strict allowlisted public observation before emitting an explicit `HOLD_*` result, fixed file-level drift/unreachable path codes, and outstanding independent proof blockers. The source identity, public HTML/Service Worker drift, current Render deploy identity, actual rollback-build eligibility and owner hardware migration are deliberately kept distinct. Even a 17/17 source match is still `HOLD_PROVIDER_RECOVERY_AND_OWNER_EVIDENCE`. It does not contain user conversations, model keys or an ability to deploy.

The workflow deliberately returns *green* when the candidate builds and the public origin is reported as **DRIFT**. This is a *successful observation*, **not** a successful public release. The added full-asset witness makes 17/17 coverage explicit and detects missing PDF files; its source-parity status cannot establish the actual provider deploy ID or rollback readiness. A green build check is **not** a production-promotion authorization. Public drift is expected until a separately approved source promotion occurs. The report never treats observed matching source bytes as proof of actual deploy identity, worker activation, offline reliability, user accounts, model-generation readiness, or device ownership.

### Manual verification without publishing

On a trusted workstation with the checked-out exact source commit, Python 3, Node, and a supported Chromium:

```sh
python3 scripts/build-studio-static.py --check
python3 scripts/test-studio-static-release-gate.py
python3 scripts/studio-static-release-gate.py --build \
  --zip /tmp/nexus-studio-static-site.zip \
  --manifest /tmp/nexus-studio-release-manifest.json \
  --source-commit <exact-40-character-git-sha>
python3 scripts/studio-static-release-gate.py --verify \
  --zip /tmp/nexus-studio-static-site.zip \
  --manifest /tmp/nexus-studio-release-manifest.json \
  --source-commit <same-exact-sha>
python3 scripts/studio-static-release-gate.py --observe-public \
  --manifest /tmp/nexus-studio-release-manifest.json \
  --report /tmp/nexus-studio-public-before-promotion.json
```

The ZIP is review/transport material: the live Render static publish directory must contain **only** its reviewed contents (equivalent to repository `public/studio`), not the outer ZIP, manifest or CI evidence JSON. Do not upload the archive or metadata as public website documents, and do not substitute a different service or workspace. The manifest is **not an independent cryptographic signature**: obtain its SHA sidecar through the actual reviewed GitHub Actions run and verify the run's source commit and provenance.

**New Phase 48 fallback:** Before any Render deployment, use the [verified previous-live public-source fallback](STUDIO-LIVE-ROLLBACK-FALLBACK.md) to retain a ZIP of exactly the files corresponding to the current live deploy, with real public HTTPS byte checks. Render supports rollback from the dashboard if the old build artifact remains retained; this has not been proven accessible through the connected Render tools. A source backup is not itself an instant provider rollback.

## Explicit human-gated public promotion

**No promotion is authorized by this stage.** The new release-decision report answers *what is still blocking release*; it cannot supply missing Render identity or prove rollback access by itself. The connected Render integration currently requires the owner to confirm the workspace before inspecting a service. Do not infer the selected workspace from an earlier dated source document. Before an actual update, the service owner must confirm the precise Render workspace, service ID/domain, source repository and branch/commit, publish directory, environment, build command, expected traffic and a currently working rollback path. Verify that no unrelated Render staged change is accidentally included. Do not proceed merely because a repository PR passed.

After separate explicit authorization, the operator may promote the **exact reviewed commit** to the verified existing static Studio service. Record the resulting Render deploy ID and actual source SHA. Require a successful deploy state, then run the existing `studio-static-public.yml` with explicit workflow dispatch on that source version, which checks exact public HTTPS source bytes and uses a new real Chromium profile for encrypted archive reopen, network-offline navigation, cache rejection and approved local model behavior. The operator should separately check the actual phone and preserve the encrypted portable archive. GitHub Actions public tests cannot prove that a real owner phone has been tested.

### Fail closed and rollback

Do not claim a public rollout if any of the following is unresolved: mismatched source bytes, 403/404/5xx or HTTPS redirect, stale/uncertain deploy ID, stale or unverified rollback deploy, missing public browser witness, CSP or service-worker integrity failure, owner archive recovery risk, insufficient permissions, or a public origin that cannot be independently observed. The release report records the drift but never silently approves it.

**Rollback protocol (manual only):** Before changing the service, record the exact current deploy/source identities and establish whether Render can restore that previous immutable deployment. If a verified public rollout fails, the authorized operator restores that **verified pre-change deployment** through Render, then reruns the read-only public checks against that previous source. Never assume that the historical November 13 initial deployment is restorable or that a rollback automatically undoes browser-cached assets. A PWA update and browser archive are separate: do not clear users' IndexedDB vaults, ask for private passphrases, or delete private project data as a rollback shortcut.

## Self-critique

- A perfect candidate ZIP can still be deployed from the wrong repository, branch, workspace or service. Therefore actual deploy authorization and recorded Render identity remain mandatory.
- CI observing a stale public site is not a deployment error. That distinction is explicit in the preflight report, and the build must not be presented as a live product update.
- Source SHA equality does not prove encrypted archives survive a particular owner phone/browser update. The previous no-upload phone self-check remains a separate manual boundary.
- Even seventeen fixed public HTTPS asset observations are not the full runtime proof. They precede, rather than replace, the real public-origin browser tests.
- The older offline Pilot 12 Issue #260 is independent from this Studio deployment, and the original Railway `/data` is still protected. `A_out <= A_in`.
