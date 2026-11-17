# Pilot 12 — public browser-wide network isolation: investigated, not cleared

Date: 2026-11-17. Scope: **read-only public Render PWA**, synthetic temporary Chromium profiles, no authenticated NEXUS gateway and no original user or Railway volume data.

## Grounded observation

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
- If the read-only witness cannot produce consistent PASS, keep issue #260 open and PR #269 **draft/unmerged**. Do not advertise permanent offline use, publish a replacement, alter user content or touch Railway data.
- Next bounded experiment: record sanitized lifecycle states of the exact registered worker (`installing/waiting/active`), controller and navigation timing before and after network cut, and compare a direct-origin disconnect with the proxy case. Treat unexpected worker lifecycle transitions as a separate failure and never print page content, bearer tokens or workspace records.

The prototype remains useful as a candidate. **Public offline resilience is currently unverified** under independently constrained browser egress; product and acceptance policy should say so.
