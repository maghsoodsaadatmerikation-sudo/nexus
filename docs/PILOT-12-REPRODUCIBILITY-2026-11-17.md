# Pilot 12 — intermittent real-public offline Chromium failure (2026-11-17)

## Evidence, not an availability claim

The `NEXUS Pilot 12 — Independent Public Installability` read-only GitHub workflow reported **PASS** for real public HTTPS Chromium twice within one run [44071274002](https://github.com/maghsoodsaadatmerikation-sudo/nexus/actions/runs/44071274002), but **FAIL** on a subsequent run [44072031139](https://github.com/maghsoodsaadatmerikation-sudo/nexus/actions/runs/44072031139). In the latter, five exact HTTPS asset checks passed; the real-browser stage failed. The sanitized failure says:

```text
stage=real-network-offline
client_error=TypeError
document.readyState=loading
has_demo=false; has_question=false; has_claims=false
has_options=false; has_decision=false
worker_controls=false
browser_offline=true
```

This contradicts a claim of consistently available public-origin offline operation. One successful run is insufficient to close [Issue #260](https://github.com/maghsoodsaadatmerikation-sudo/nexus/issues/260). Do not infer a new release, permanent installability, device compatibility, or recovery availability.

## Narrow change

The historical public application / manifest / worker bytes stay sourced from the immutable `35be3d4b0da0d0f21e04a4a8a61f45e316a0058e` baseline with the original witness blob pin, not the newer candidate. `scripts/prepare-public-pilot-witness.sh` retains the original runtime assertion (fictional question, two claims, two options, **no human judgment**) and failure-only boolean diagnostics. Before that single click it additionally requires:

1. The real offline document reports `readyState === complete`, its expected UI nodes are present, and the reviewed schema marker is in the DOM.
2. Browser is actually offline, and `navigator.serviceWorker.controller.scriptURL` matches the current origin's exact worker.
3. The full document URL matches the public origin, and two observations 300 ms apart share the same document `performance.timeOrigin`. A changing document, error page, absent controller or slow boot cannot pass.
4. The existing two separate fresh Chromium profiles, exact public asset byte checks, and unmodified negative assertions remain required.

This change **cannot repair a service worker or CDN failure**. It prevents a misleading success based on a transient ready-state and makes a persistent failure fail closed, closer to its cause. It does not alter deployed HTML, cache data, Render settings, keys, user content, or Railway storage.

## Completion gate

- GitHub PR tests must verify the pinned baseline, script syntax and candidate tests.
- Repeat the real-public observer across fresh Chromium profiles and separate runs. Any intermittent failure keeps Issue #260 open.
- If failure persists, instrument only public-safe CDP navigation/worker lifecycle signals and identify the response status and controlling worker; never loosen the production assertions to force green.
- Any eventual deployment correction requires reviewed source, explicit Render promotion and independent re-observation. No provider write is authorized by this PR.
