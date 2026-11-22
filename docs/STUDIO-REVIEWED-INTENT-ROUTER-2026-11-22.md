# NEXUS Studio: safe deterministic chat routing (draft)

This draft augments existing chat-first intent routing, without adding any autonomous model planner or permission to act. Explicit ordered English/Persian sequences of 2–6 recognized steps now open the **Review multi-step plan** preview rather than collapsing into one tool. A second explicit click is required to build a local review-only checklist; actual actions retain their separate consent and fresh-result conditions.

Narrowly recognized native image/video generation or editing requests, including `/image`, `/video` and `/animation`, are refused as unsupported in this Studio build. The explanatory panel offers a separately reviewed **text-only** model or guide route, but does not claim that media was generated. Single-tool proposals explicitly say that runtime success is unverified and link to the opt-in authenticated capability inventory, which remains no-network until separately requested.

This is bounded deterministic syntax matching, not natural-language understanding. Ambiguous input remains in the composer; unknown tools and provider calls are not guessed or automatically executed. The original draft remains intact. The Chromium acceptance script checks English/Persian ordered intents, unsupported media, no hidden provider calls and invalidation on edits. Standalone, SRI, service worker and offline static package must be rebuilt and verified on exact head before any merge. Do not deploy this draft. All commits include `[skip render]`.

## Regression fix: reviewed fallback remains reachable

The primary chat toolbar already contains the persistent **Tool status** button. Adding a *second* status button inside every single-tool offer broke the established three-button order and its local-guide fallback in real Chromium. The redundant offer button was removed; the original **Open tool / Continue with guide or model / Keep typing** ordering is restored. Both an ordinary Studio browser acceptance assertion and the extended chat tool-handoff witness check it. No consent, provider credentials, or network behavior were changed by the fix.
