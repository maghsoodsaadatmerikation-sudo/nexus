# NEXUS Studio — local credential preflight (22 November 2026)

## Purpose

The user can approve the exact content of a model request, including selected
memory, prior messages, sources and extracted file excerpts. That request may
inadvertently contain a private credential. This patch adds a **client-side,
non-exhaustive and non-echoing warning** for recognized credential shapes
*before* a human sends a request to a remote model gateway.

## How the safeguard works

1. Studio constructs the same bounded `ctx.messages` array that will be shown
   during exact-context review and forwarded on approval. It does not inspect
   only the latest input field.
2. For **remote** gateway requests only, `NexusStudio.inspectSecrets` scans
   those exact messages for recognizable private key headers, GitHub access
   tokens, model API keys, AWS access keys and long Authorization Bearer values.
3. The warning contains **only fixed labels** for the risk categories — not
   matches or excerpts. Model context review remains available.
4. When a pattern is present, the usual consent checkbox and a **second
   independent checkbox** are both required. The actual send handler checks
   both, so an enabled/disabled control alone cannot bypass this protection.
5. Changes to the prompt, context options, model, thread, gateway, language
   import state or a lock/clear operation revoke the reviewed request and both
   checkboxes. The warning is retranslated when switching between English and
   Persian without preserving a stale approval. A normal clean request does
   not inherit an earlier override.

The local on-device model does not contact a remote provider and has no
extra remote-transfer warning. Every remote gateway still requires its
original exact-message review and consent.

## Boundaries

This is **not comprehensive data-loss prevention**: unknown credential
formats, encoded/obfuscated values, arbitrary private information or new
providers may escape detection. False-positive warnings are possible.
The user remains responsible for reviewing the full request; the separate
override does not redact any text automatically. An approved remote provider
can see whatever the user approves sending.

The scanner never tries to validate a credential or send a test request.
It yields only fixed category names and never saves matched values, and it
does not add telemetry, background checks, new cloud dependencies, provider
credentials or autonomous actions.

## Test and static package evidence

```sh
node scripts/test-studio-core.mjs
python3 scripts/build-studio.py --check
python3 scripts/build-studio-static.py --check
python3 scripts/test-studio-credential-preflight-browser.py
```

Synthetic fixtures cover positive and negative pattern recognition, multi-turn
inspection, non-echoing reports, invalid input, fresh consent, button and
handler guard behavior, language changes, approval revocation and one
mock-only transmission after two deliberate approvals. Tests in Chromium
run both narrow and wide viewports; no real remote provider is contacted.

Both standalone and static HTML were generated from the reviewed source,
and the offline service worker has an independently recalculated exact
HTML SHA-256, byte length and cache package identity. The strict static
HTML-only size limit is 635,000 bytes; every other asset limit remains fixed.

No publication, external provider setup, billing or production rollout is
authorized by this draft.
