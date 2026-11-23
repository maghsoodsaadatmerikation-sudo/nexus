# Studio reply readability and safe code copying — 24 November 2026

## User-facing improvement

The focused chat now renders additional **finished model reply** Markdown features:

- `~~obsolete~~` becomes semantic struck-through text.
- `- [ ] Open` and `- [x] Finished` become **disabled, read-only** checkboxes, with clear accessible status. They do not trigger tools or change project state.
- A standalone `---`, `***` or `___` creates a thematic separator.
- Fenced code preserves exact literal bytes, and a strictly validated single-word language identifier is exposed as inert code metadata.
- In the live chat (not exported HTML), a **Copy code** / **کپی کد** button copies only the fenced snippet following an explicit click. Clipboard failures show an honest unavailable message.

Existing HTML and image tags remain inert text. Only approved HTTPS links become anchors. Nothing is sent to a provider, executed, persisted, or automatically copied by these presentation-only additions.

## Output contracts

- The original response Markdown remains unchanged in the conversation, copy-whole-answer, Word and transcript paths.
- Standalone HTML preserves semantic task states, strike-through and separators, but **excludes clipboard buttons**; its restrictive Content Security Policy remains unchanged.
- Live copy buttons use the browser clipboard API directly and only when clicked; unsupported browsers report failure rather than attempting an unsafe fallback.
- Generated `web/studio.html` and `public/studio/index.html` mirror the reviewed source, and the public offline service worker hash, byte count and cache ID are regenerated from the updated HTML.

## Verification

```sh
python3 scripts/build-studio.py --check
python3 scripts/build-studio-static.py --check
python3 scripts/test-studio-browser.py
node --check web/studio-reply-format.js
node --check web/studio-app.js
```

The real-Chromium fixture now checks literal code, task states, strike-through, separators, safe links, exact snippet copying, transcript integrity and inert export. These synthetic tests do not provision a generative model, prove model quality, or authorize a production deployment.
