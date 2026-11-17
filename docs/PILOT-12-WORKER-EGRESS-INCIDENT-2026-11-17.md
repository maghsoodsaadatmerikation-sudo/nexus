# Pilot 12 — public Service Worker egress investigation and verified browser witness

Date: 2026-11-17. Scope: **read-only public Render PWA**, synthetic temporary Chromium profiles, no authenticated NEXUS gateway and no original user or Railway volume data.

## Initial failure observations (before the corrected witness)

Previous public HTTPS PWA tests alternated PASS and FAIL on the same published source. Earlier "offline" checks used CDP `Network.emulateNetworkConditions` on the **page target**, which does not independently prove that a separate Service Worker target cannot fetch from the network. In a local Chromium corrupt-cache experiment, the page claimed offline while the worker still produced a valid network-first 200 response (see merged PR #268 and issue #260).

Draft PR #269 introduced stronger, **deliberately fail-closed** independent public-origin probes. Experimental approaches found:

- With page and worker-target CDP network emulation, Chromium produced a browser network error before the worker could deliver a cached HTML response. This is a browser-target test behavior, not proof that the published Service Worker code is defective.
- With worker-only target emulation, the page could still produce an online HTTP 200 not delivered by the Service Worker. Such a response must **never** be counted as an offline success.
- A disposable local HTTP CONNECT proxy routed Chromium's public HTTPS requests to the **one reviewed origin** only, then rejected all new tunnels and destroyed active ones after Service Worker installation. On an observed run with the separate page network emulation removed, its sanitized counters were `allowed=3`, `blocked=16`, `unexpected=13`, `active=0`, `live=false`. The navigation then reported a browser error, **not** a proven Service Worker cache response. See [GitHub CI run 44104141330](https://github.com/maghsoodsaadatmerikation-sudo/nexus/actions/runs/44104141330).

The non-allowlisted attempts were **denied**; their destinations were not logged. At this stage the exact root cause (Chrome proxy/service-worker lifecycle vs a defect in the live PWA) remains unproven. A failing browser egress test is not equivalent to a confirmed user-visible outage on all devices, but it prevents a defensible offline-readiness claim.

## Security and acceptance boundary

- Never interpret `navigator.onLine=false` alone as proof the worker lacks internet.
- Never accept a direct online 200 or a browser error page as a successful cached navigation.
- Require a verified exact-source cache, worker control + registration state, a genuinely unavailable origin path, and an independently observed worker-served document in the **same test profile**.
- Retain the original eight product-contract checks and four independent real-public fresh-profile witnesses; do not replace the deployed app with unpublished candidate files.
- Until the read-only witness produces repeatable exact-source PASS, keep issue #260 open and PR #269 **draft/unmerged**. Do not advertise permanent offline use, publish a replacement, alter user content or touch Railway data.
- Next bounded experiment: record sanitized lifecycle states of the exact registered worker (`installing/waiting/active`), controller and navigation timing before and after network cut, and compare a direct-origin disconnect with the proxy case. Treat unexpected worker lifecycle transitions as a separate failure and never print page content, bearer tokens or workspace records.

These initial failed experiments did **not** demonstrate reliable public offline resilience. The follow-up below supersedes this preliminary acceptance status while preserving the failures as evidence.

## Follow-up: corrected browser witness and repeated acceptance

The historical witness performed `Page.reload({ignoreCache:true})`, which
corresponds to a hard reload and can bypass the Service Worker. This is not a
normal user reopening the app. The test-only candidate now uses an ordinary
reload, while retaining a genuine browser HTTPS CONNECT-proxy tunnel cut,
zero active egress tunnels, the exact source hash, worker controller, navigation
`workerStart`, worker-origin 200 document observation, and the eight original
product-contract assertions. An ordinary online 200 or a Chrome error page
cannot satisfy the offline test.

The first ordinary-reload candidate passed once, but its same-code rerun
failed *before network cut*, at the opt-in installation step. A complete app
document and secure context were present, yet no active Service Worker,
registration or app-shell cache existed. A later diagnostic-only direct
registration resolved, suggesting an intermittent opt-in/bootstrap
readiness issue, not proving its exclusive cause.

To prevent premature synthetic clicks, the corrected test now waits for the
actual button's registered DOM `click` event listener using read-only CDP
`DOMDebugger.getEventListeners` before invoking the real app handler once.
This adds no production code, permissions or registration bypass.

**Repeated real public-source Chromium acceptance:**

- [Run 44123804250, attempt 1](https://github.com/maghsoodsaadatmerikation-sudo/nexus/actions/runs/44123804250/attempts/1): PASS, four isolated profiles
- [Run 44123804250, attempt 2](https://github.com/maghsoodsaadatmerikation-sudo/nexus/actions/runs/44123804250/attempts/2): PASS, four new isolated profiles
- Both attempts used the same reviewed candidate SHA
  `2550be47532ebf3ddc75cbf39087a7a9ad6d153e` and the exact pinned
  historical **published** app/worker/manifest. Both required exact online
  cache identity and Service-Worker-delivered cached document after actual
  network tunnel cut. Neither touched real user content or authorized a deploy.

**Scope:** two independent green CI attempts give evidence that the old
published PWA can be reopened offline in these disposable Chromium profiles
under a normal user-style reload. They do not verify Android hardware, all
networks or browsers, or any other Studio app, and they do not authorize a
release or certify production data durability. Repeat the gate after relevant
source, Chromium or network-environment changes. Any future red run must stay
red and be investigated, not retried until accepted by chance.

The public application bytes and Render configuration remain unchanged.
