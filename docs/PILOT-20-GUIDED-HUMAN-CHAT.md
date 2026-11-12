# Pilot 20 — Human-centred guided conversation (offline)

## Meaning of "Chat with NEXUS"

This stage adds a usable, two-way **human ↔ NEXUS guide** conversation panel.
The human writes a turn and NEXUS responds with a grounded **scripted
reflection prompt**, chosen from a six-stage cycle (clarify, evidence,
alternatives, uncertainty, values/consequences, reflect), or a stage manually
selected by the human. The human may converse over multiple turns. The system
repeats a bounded excerpt from the latest message so the prompt refers to
something the person actually wrote. Previous turns remain visible.

**This is not an LLM.** There is no trained generative model, live human peer,
server chat API, authenticated human-to-human messaging, automatic facts
from the Web, memory-based personalization, fact verification or autonomous
recommendation. It must never impersonate an intelligent model or a person.
A separate, explicitly reviewed model integration would require a provider
contract and separately consented/secured data transfer. It is not claimed here.

## Boundaries and workflow

- English-first, complete Persian catalog, plus local user-installed packs.
  Switching locale does not rewrite existing personal conversation turns.
- Users can type at most 1,500 Unicode characters per message; a transcript
  holds at most **40 human/guide exchanges** (80 messages). Every message
  and reply is rendered as inert DOM text; no HTML evaluation or remote code.
- Optional **Use committed workspace context** checkbox is OFF by default.
  When enabled, the next scripted reply can refer to the recorded question,
  number of registered claims, number of alternatives and up to three
  registered value labels. This is a summary of user-supplied state, not
  validation of claims. The chat does not read passwords, user-file bytes,
  research queries, analytics data, unregistered drafts or audio.
- The person can explicitly copy their most recent *human* message to either
  an unregistered question draft or an unregistered human-origin evidence
  draft (uncertainty unknown). The source is not fabricated. Nothing is
  registered until the person submits existing workspace forms, preserving
  the constitutional authority boundary `A_out <= A_in`.
- The conversation and its unsent draft are in tab memory only, excluded
  from all workspace exports, the encrypted workspace checkpoint, Rust
  transfer and local file-desk bundles. Draft protection warns about
  replacement and browser exit; a new/replaced/restored workspace clears
  this private chat. Force close can still lose data.
- Explicit **Download conversation** emits an unencrypted TXT transcript
  only after consent. It can contain private content. Device-side saving and
  any onward human sharing are not independently verified. **Clear
  conversation** requires confirmation and does not change the workspace.
- An optional **Read latest reply** button uses only a browser/device voice
  advertising `localService === true` in the active language. It must never
  start automatically and must not silently choose a provider-hosted voice.
  Availability and quality vary by device. No live microphone/chat
  transcription is promised by this stage; existing Voice tools remain
  separate.
- Static HTML and browser app preserve `connect-src 'none'`. This component
  makes no application network requests or persistent plaintext writes.
  The separately existing optional encrypted workspace resume continues to
  function but never persists chat turns.
- These prompts are designed for evidence-aware discussion; they are
  **not independent medical/legal/financial advice**, clinical judgment,
  genuine reasoning inference or a human replacement. No bot turn can
  append a human judgment or audit event.

## Acceptance and release gates

- `scripts/build-ui-languages.py --check` verifies the authored chat core
  matches standalone HTML, that complete English and Persian catalogs match,
  and that the installed offline worker's SHA-256 is exact.
- `node --check web/guided-chat-core.js` enforces standalone script syntax.
- `scripts/test-guided-chat-browser.py` uses real isolated Chromium in two
  viewport classes: initial empty state, six linked conversation phases,
  focused stage switching, XSS-inert messages, separate user-controlled draft
  flows, consent to read committed context, password non-disclosure, no
  workspace mutation, local-only voice using a *synthetic native adapter*,
  confirmation before transcript export/deletion, English/Persian switching,
  new-workspace cancellation and clearing, 40-turn limit, and zero network
  or plaintext localStorage writes. Native real-device TTS remains untested.
- Existing offline, file, data analysis, language, voice, Rust gateway,
  privacy, authentication and resilience gates continue unmodified.
- Only after all exact-head PR checks pass may code merge to `main`.
  Public status additionally needs the **existing static Render site**
  manually deployed to the exact merged HTML source and an independent
  public HTTPS exact-byte, Chromium and offline-reopen witness. No new paid
  service, no protected Railway volume mutation and no release seal.

This phase offers an honest, useful, deterministic conversational foundation
on the current zero-budget static architecture. Future live AI chat or
peer-to-peer conversation would be a distinct design, security and consent
milestone.
