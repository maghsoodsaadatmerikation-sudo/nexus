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
4. The workflow now requires **four** independently created Chromium profiles against real public HTTPS, all preserving the eight original assertions and exactly observed immutable assets. Any single failure aborts the gate; it cannot be retried away to manufacture green.

On a public-offline failure, the pinned browser witness also emits a capped, content-free CDP trace: whether a navigated frame matched the exact known origin, whether Chromium visited a browser-error page, whether the Document response was HTTP 200 HTML served by a Service Worker, and whether a Document load was aborted/disconnected. It never prints full URLs, page text, request headers, tokens, workspace content or private files. This is diagnostic evidence, not an alternate PASS route.

This change **cannot repair a service worker or CDN failure**. It prevents a misleading success based on a transient ready-state and makes a persistent failure fail closed, closer to its cause. It does not alter deployed HTML, cache data, Render settings, keys, user content, or Railway storage.

## Completion gate

- GitHub PR tests must verify the pinned baseline, script syntax and candidate tests.
- Repeat the real-public observer across fresh Chromium profiles and separate runs. Any intermittent failure keeps Issue #260 open.
- If failure persists, inspect the bounded CDP navigation response/failure trace, compare all fresh profiles, and distinguish Chrome network emulation from a genuine worker navigation failure; never loosen the published application or the production assertions to force green.
- Any eventual deployment correction requires reviewed source, explicit Render promotion and independent re-observation. No provider write is authorized by this PR.
