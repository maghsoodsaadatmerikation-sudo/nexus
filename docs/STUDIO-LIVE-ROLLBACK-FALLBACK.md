# Phase 48 — independently matched previous-live Studio source fallback

## Current provider facts (read-only Render observation, 19 November 2026)

The connected Render workspace confirmed the existing **public Studio** static site:
- Service: `nexus-studio-merikation`, `srv-dbrjurc9v7es73cqe0v0`; workspace: `tea-dabhioe10ojc73acbs8g`.
- Public origin: `https://nexus-studio-merikation.onrender.com/`.
- **Currently live deploy at this observation:** `dep-dbvkuonf3r2c73cj3930`.
- **Currently live Git source:** `9e05b840fc2d36d7bc268aede2693ab4d6fb08e3` (19 November 2026, Studio fallback review, PR #321).
- Repository: `maghsoodsaadatmerikation-sudo/nexus`; branch `main`; build check `python3 scripts/build-studio-static.py --check`; published directory `public/studio`; AutoDeploy **OFF**.

The previous successful deploy `dep-dbvgqotg1s2s73f6ghtg` from `e4f24218d7a3882391b593d78641d7a5ff50866d` is now deactivated. The fallback tool, tests and workflow pin the confirmed live deployment above.

This is a time-stamped **provider metadata observation**, not proof that the public origin actually serves the same code. That independent claim requires the fallback workflow's read-only nine-asset HTTPS comparison to succeed. Re-read the Render deployment metadata immediately before promotion; an archived fallback becomes stale if the live site changes. The source ZIP does not prove the Render provider retained the old build artifact.

Render [official rollback documentation](https://render.com/docs/rollbacks) says a service can be rolled back from its Dashboard **Deploys → recent successful deploy → Rollback → Rollback to this deploy**, or with Render's rollback API, **but only while that previous deploy's build artifact remains retained**. Current connected Render actions permit `get_deploy`/`list_deploys`/`trigger_deploy`, but do not expose **rollback** or test the retained artifact. Therefore the existence of a live historical deployment record **must not be presented as proof** that an instantaneous rollback can currently be executed through this chat.

## Concrete independent source fallback

The [Previous-Live Public Source Fallback workflow](https://github.com/maghsoodsaadatmerikation-sudo/nexus/actions/workflows/studio-live-source-fallback.yml) checks out the exact current **public static source** commit at the recorded snapshot alongside the current reviewed tool code, verifies that the 13 allowed `public/studio/` files have not changed, and performs nine **actual read-only HTTPS GETs** against the public origin (HTML, service worker, manifest, icons and four device modules). It requires exact bytes for **seven code/manifest files** and canonical decoded RGBA pixel identity for **two PNG icons**, because Render can reencode PNG containers without changing the image. An unavailable URL, changed HTML/JS/worker, changed image pixel, or wrong historical source blocks publishing.

If all checks pass, the workflow publishes for 30 days: `nexus-studio-previous-live-source.zip`, its independent SHA-256 sidecar, and `nexus-studio-previous-live-witness.json` containing source/deploy IDs and the nine verified path statuses, explicitly marking pixel-equivalent icons as `PIXEL_MATCH` when raw PNG bytes differ. The source ZIP contains exactly 13 **public code** files and **no** archive, user chats, keys, passwords, runtime model weights, private environment variables, provider tokens or Railway data. Source commit and public bytes are pinned independently of Render's cached build artifact.

## Recovery and future publication sequence

1. Before touching Render production, save the successful fallback CI artifact and verify ZIP SHA-256 against its separate Actions sidecar. Record the Render live deployment ID, source commit, service, branch, build command, publish path and exact prior public origin. Do not assume the currently displayed provider state will remain unchanged.
2. In the [Render service dashboard](https://dashboard.render.com/static/srv-dbrjurc9v7es73cqe0v0), open Deploys and **confirm** the old live build artifact is actually rollback-eligible. If this cannot be confirmed, do **not** claim instantaneous rollback readiness. This public-code ZIP can support a separately reviewed deploy of the old Git commit, but by itself is **not** a Render rollback, a recovery of browser IndexedDB data or an authorization to change production.
3. Receive explicit owner approval for the exact source change to this exact static service. The existing `trigger_deploy` connector is only a latest-branch deploy operation: it does not accept a source SHA or previous deploy ID. If the branch advances, it could deploy a different commit; do not use it to pretend a particular SHA was promoted or that automatic rollback is available.
4. After approved deployment, independently record the **new** Render deploy ID and successful status, then dispatch the [Phase 47 Public Studio Witness](https://github.com/maghsoodsaadatmerikation-sudo/nexus/actions/workflows/studio-static-public.yml) on the exact promoted source commit. It requires nine public source matches, two independent real Chromium offline/encrypted-vault sessions and the actual pinned small-model test. Do not conflate a source ZIP with live readiness.
5. If public acceptance fails, perform manual rollback **only with the verified Render Dashboard provider feature** and independently revalidate the prior public origin. If the old build artifact is unavailable, an authorized operator may separately rebuild and deploy the old source; this is not a verified zero-downtime rollback. Keep user browser storage and private encrypted archives untouched.

## Self-critique and honest limits

- **Source fallback is not an instantaneous Render rollback:** the installed Render connector has no rollback operation, and provider build artifact retention is not exposed by the read-only service/deploy APIs. The report explicitly sets `rollback_render_build_artifact_confirmed:false`, `rollback_action_available_in_connector:false` and `actual_rollback_executed:false`.
- **Public source-byte parity can change:** the workflow runs against the actual live HTTPS origin. It fails closed after the new site is promoted; rerunning it *after* rollout cannot establish the old site remains live. Preserve the successful pre-promotion artifact separately.
- **Public images can be reencoded by a CDN:** exact icon bytes are not equivalent to image identity, so the existing bounded PNG decoder compares all RGBA pixels and rejects malformed or different images. The seven public nonimage assets remain byte-exact. The other four reviewed files are pinned to the exact historical Git commit, not inferred from remote public responses. The source ZIP has all 13 allowed assets and refuses unexpected members. This is a source recovery path, not a verified Render build-artifact restore.
- **No user-generated data is involved:** browser encrypted archives and the original Railway Stage D `/data` Volume are outside this static site package. Reverting public code does not automatically recover or delete user data.
- **No deployment executed in Phase 48:** this phase is an independently auditable precondition, not approval. Avoid creating a new paid service, changing Render AutoDeploy, or triggering a provider release until the owner explicitly authorizes the exact action.
