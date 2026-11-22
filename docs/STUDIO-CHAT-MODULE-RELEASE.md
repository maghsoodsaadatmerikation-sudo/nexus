# NEXUS Studio — public chat module split (candidate)

## Scope

The self-contained `web/studio.html` is deliberately unchanged and can still
open as a single local file. Only the installable static site separates the
existing reviewed chat compositor into
`public/studio/modules/studio-composer-ui.js`. All other Studio components
remain in the ordered standalone bundle for now.

The site builder matches exactly one inline `<script>…</script>` block whose
bytes match `web/studio-composer-ui.js`. Missing, duplicated, edited or
out-of-order source fails the existing checked source build. It swaps that
single block for a synchronous, same-origin external script **at precisely the
same position** in the HTML. The following local modules retain their order.
There is no dynamic import, eval, external CDN or additional provider request.

## Integrity and offline guarantees

- The served script has a built-time SHA-256 Subresource Integrity attribute.
  A mismatched online response must not execute in the browser.
- The exact script bytes and hash are included in the offline Service Worker's
  reviewed `CODE` manifest and cache identity; install/refresh accepts a
  same-origin, correctly typed, non-redirected response with matching length
  and SHA-256 only.
- The installable HTML itself is still hash- and length-pinned. A new revision
  has a new cache identity; previous caches are cleared after activation.
  Missing or corrupted offline assets fail closed, rather than being trusted.
- The reviewed allowlist gains exactly the module path. Symlinks, extra files,
  content drift and unknown assets remain rejected by public-tree checks.
- The Studio maintenance allowlist includes the generated module so the repair
  checker can track it without unintentionally changing unrelated files.

The static index is now about 596 kB, leaving room below the strict
645,000-byte per-asset cap. The external chat module is roughly 49 kB.
This is **not** a decrease in total script bytes or bandwidth; it is a
bounded first step to modular, independently verifiable future updates.

## User-facing behavior

Chat, bilingual plan previews, tool result receipts and explicit permission
review should behave identically. The browser obtains the module from its
**same origin**, even while online; it contains only public application code,
not account secrets, chat history, prompts, stored projects, credentials, model
weights, or user audio. Those remain subject to existing in-browser controls.

No provider network traffic, user-data upload, model request, autonomous task
execution, public release or production deployment is part of this patch.

## Acceptance and rollout

The exact-head CI must pass static source release, real desktop/mobile Chromium,
offline first-load/reopen, strict asset integrity, Studio chat handoff and
independent PR verification. A missing script, changed hash or missing cache
asset is a blocking defect. The change is intentionally a stacked *draft*
following reviewed assistant PRs. Do not merge or deploy before reviewing the
entire stack and the final production release witness.
