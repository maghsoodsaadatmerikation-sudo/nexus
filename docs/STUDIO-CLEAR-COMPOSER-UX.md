# Phase 43 — One clear chat action, explicit model review and truthful save state

## Problem observed

NEXUS Studio Phase 42 makes mobile navigation clearer, but the conversation still exposed separate **Use local reflection guide**, **Prepare model request**, **Prepare another answer**, **Stop**, the optional model settings and a distant private archive. First-time users could mistake local rule-based guidance for AI generation, or believe that merely composing a draft or unlocking a vault meant it was permanently saved.

## Implementation

1. The mobile focus view has **one composer action**, labelled according to a visible answer-mode selector: **Local reflection guide** (default) vs **Review AI model request** (opt in). Desktop full view keeps all original buttons. The mobile original guide/prepare/regenerate actions remain present and callable through the tested app, but are visually deemphasized; the Stop action remains visible.
2. **Local** delegates to the existing `guide` button and its reviewed validation, including refusal when the requested turn requires temporary file excerpts. It is explicitly called a *non-generative guide*. The new component cannot call model APIs.
3. **Model** delegates only to the existing `prepare` button. No request is sent: the existing exact-context preview, consent checkbox and separate `send-model` action remain mandatory. A visible **Model settings** shortcut opens the preexisting configuration panel; choosing model mode or opening settings makes no network call and imports no new authority.
4. **Explicit save** shortcut: if the encrypted vault is locked, it routes to the existing Archive tab and its passphrase entry; if unlocked and the existing no-forms gate is satisfied, it triggers the audited vault `save` button. If unsaved chat text, attachments, attached document or unapplied profile/editor draft exists, the shortcut is disabled; the existing app never promises autosave. Users are reminded to keep a *separate* encrypted backup.
5. The status note distinguishes **archive locked**, **unapplied/unsaved draft**, and **vault unlocked** without making an independently unverifiable 'everything saved' promise. The Studio app exports only minimal **read-only booleans** for the UI and dispatches a local DOM state event after its preexisting controls refresh. No new browser storage key, telemetry, provider token, request path or background operation.
6. **Accessibility:** >=44px touch targets, an explicit label for the answer mode, text that respects English/Persian language choice, status announcement without copying private prompt text, Ctrl/Cmd+Enter shortcut to the *same reviewed first action* (model mode only reaches review), and keyboard focus on the existing review heading. Empty-message actions remain disabled.

## Self-critique and regression constraints

- **A shortcut must not bypass human consent.** In model mode the quick action never clicks `send-model`, never checks `consent`, and never submits a request automatically; CI explicitly tests that an unconfigured model cannot send, including Ctrl+Enter.
- **Do not confuse 'Save' with autosave or lose drafts.** Quick save refuses a nonempty composer, temporary attachments and unapplied forms; it routes locked vaults to passphrase setup and otherwise runs only the original encrypted `save` implementation. The status text does not promise that a server or another device holds a backup.
- **Model access is optional, not a ChatGPT subscription privilege.** The static server hosts no frontier model. The model settings shortcut only reveals controls. An optional on-device small model and an operator-configured gateway still require separate setup; all previously enforced capacity, provider and context limits remain.
- **Avoid controls duplication.** The new composer is shown only in focused view. The earlier multi-button panel remains in the full-layout desktop mode, ensuring no accidental loss of advanced features.
- **Retain offline integrity and device isolation.** Rebuild `web/studio.html`, public PWA `index.html`, and its digest-pinned service worker from reviewed sources; the same code is tested both on loopback and in the source-bound phone ZIP. Existing browser archive encryption and opt-in cache semantics are unchanged.

## Verification

`scripts/test-studio-static-browser.mjs` adds checks for the honest initial mode, no-model refusal without any model POST, Ctrl+Enter non-transmission, correct local quick action, explicit vault setup routing, real encrypted quick-save, draft-save refusal and Persian labels. The old live PWA and Studio core suites still run. A green Chromium CI result does not constitute Android hardware or real-network-provider acceptance.

**Deployment**: GitHub merge does not deploy Render (AutoDeploy disabled). Railway original Volume and sleeping service are untouched, Stage D recovery remains blocked by absent actual owner-held key/provider capture proof, and no production release authority is created.
