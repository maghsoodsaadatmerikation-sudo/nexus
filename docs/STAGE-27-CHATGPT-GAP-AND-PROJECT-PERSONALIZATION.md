# Stage 27 — ChatGPT capability-gap audit and first integrated parity components

**Reference:** 2026-11-13. Human-authored, source/repo-aware gap assessment;
not an assertion that NEXUS has equivalent LLM capability.

Official ChatGPT reference:
- https://help.openai.com/en/articles/9260256-chatgpt-capabilities-overview
- https://help.openai.com/en/articles/10169521-projects-in-chatgpt
- https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex
- https://help.openai.com/en/articles/8555545-uploading-files-and-audio-to-chatgpt
- https://help.openai.com/en/articles/11487775-apps-in-chatgpt

NEXUS actual source:
- README.md, web/offline-pilot.html, web/research-chat.html,
  web/chat-history.js, web/connections.html, web/data-analysis-core.js
- docs/PILOT-15 through PILOT-20, docs/OPTIONAL-CHAT-HISTORY.md,
  docs/OPTIONAL-APP-CONNECTIONS.md, docs/WORK-MODE.md
- docs/STAGE-25-NATIVE-OFFLINE-ANDROID.md,
  docs/STAGE-26-ANDROID-EMULATOR-ACCEPTANCE.md

"Partial" means an implemented subset or prototype, **not** parity.
"Missing" means no supported equivalent product capability is established.
"Stage27 development" means new code and tests in a development PR only.
The original production Railway gateway and offline Android APK from Stage25
remain separate from all unmerged development capabilities.

| ChatGPT capability | NEXUS status | Exact gap / independent acceptance |
|---|---|---|
| Generative multi-turn AI chat and reasoning | PARTIAL | Read-only citation-oriented extractive chat exists; no general LLM inference, reliable reasoning/model selection. Needs opt-in model backend, privacy and quality eval. |
| Current web search | PARTIAL | Consent-based bounded Wikipedia/DDG public research; not every search engine or unrestricted browser. Needs explicit domain allowlisting, primary-source citations and freshness observations. |
| Deep research | MISSING | No autonomous multi-step multi-source synthesis. Needs planned research, evidence citations, budgets, source diversity, uncertainty and independent result evaluation. |
| Read uploaded images / visual reasoning | MISSING | File bytes can be attached, not interpreted by a visual model. Needs permissioned vision provider or real on-device vision model and privacy checks. |
| Generate and edit images | MISSING | No generative image model or image-edit service. Needs model, user consent, pricing/quotas, rights and safety. |
| Generate and edit video | MISSING | No media generation pipeline. Needs models, render/storage budgets, moderation and verified exports. |
| Speech conversation / live voice | PARTIAL | Local/consented browser speech capture/read-aloud on separate static pilot. Not live multimodal dialogue or native Android mic/audio. Needs real phone tests and offline/online service disclosure. |
| Native multilingual conversation/translation | PARTIAL | English/Persian UI and importable language packs; not model-level multilingual translation. Needs language modeling + per-language quality tests. |
| Files and document understanding | PARTIAL | Local tray and bounded DOCX/XLSX/PPTX text extraction; PDF/image/audio transcription absent, Android file input bounded. Needs safe parsers and tested output. |
| Data analysis and graphs | PARTIAL | Local CSV/TSV/JSON/XLSX descriptive analysis and simple charts; no sandboxed Python/SQL/code execution, no general scientific analysis. |
| Generate PDF/DOCX/XLSX/PPTX | PARTIAL | Static pilot makes some text-based document exports; no complete editable presentations or high-fidelity universal file builder inside native APK. |
| Persistent encrypted conversation history | PARTIAL | Development gateway supports opt-in local encrypted history, not native APK, shared cloud history or multi-device continuation. |
| Projects and Work Mode | PARTIAL | Human-authored task plans, dependencies, notes, files, explicit review and AES archive; not autonomous agent execution. |
| Custom assistants / Custom GPTs | STAGE27 DEVELOPMENT | Per-project name/style/instructions, encrypted and user-owned; **no** trainable GPT/model, tool execution, sharing, public assistant store. |
| Memory and personalization | STAGE27 DEVELOPMENT | Explicit user-reviewed project-scoped encrypted memory only; not semantic cross-chat auto-memory, global profile or sync. |
| Scheduled tasks, alerts and monitoring | MISSING | No durable hosted scheduler and delivery system. Requires worker, persistent queue, user control, timezone and cancellation proofs. |
| App connections / plugins | PARTIAL | Development gateway has operator-reviewed read-only MCP, explicit per-call consent; no general user OAuth, plugin marketplace, or write actions. |
| Agent/Work computer and browser use | MISSING | Only human Work planner; no sandboxed cloud computer/web interaction or verified execution approvals. |
| Coding assistant / repository agent | MISSING | Core Rust dev tests exist, but no user-facing isolated code agent/repo editing/CI review. |
| Custom multi-model selection | MISSING | No inference model registry or provider quality/economy controls. |
| Persistent personal account and multi-device sync | MISSING | Some local archives transferable manually; no account identity, authenticated end-to-end encrypted sync or conflict resolution. |
| Collaborative/shared projects | MISSING | No team RBAC, invited member sharing, audit identity or workspace isolation. |
| Rich interactive maps and live commerce/reservations | MISSING | No provider-backed interactive map, product inventory or real-time reservations tool. |
| Advanced safety/quality evaluations for model output | PARTIAL | Strong human-authority and verification contracts; not broad model hallucination, bias, safety or frontier evaluation. |
| Offline Android app | PARTIAL | Test APK built and verified on real Android emulator; no owner-device pilot, durable signing key or Play Store release. |

## Priority and dependency order: one capability per independently testable gate

1. **Stage 27 (this PR)**: custom project assistants and user-reviewed opt-in
   project memory, bounded and encrypted using existing NEXUS Vault.
   Tests reject unsafe shapes and secret spill; a preview is never sent without
   the existing explicit network consent. This is NOT general GPT intelligence.
2. Stage 28: independently tested Android SAF file save/readback and encrypted
   restore, then real Android owner-device acceptance.
3. Stage 29: opt-in privacy-safe hosted inference adapter with exact model identity,
   bounded input/output, cancellation, explicit cost/source disclosure and no
   auto-execution. Requires operator-approved credentials and potentially fees.
4. Stage 30: multiple source verified web research + independent citation
   evaluation, sources and provider consent. No automatic web access without it.
5. Stage 31: image input & media pipelines with user-selected provider, privacy,
   latency, cost and media rights checks; model/media services may not be free.
6. Stage 32: true model-level multilingual dialogue and native speech with
   Android device acceptance. Browser voice alone is not a live voice model.
7. Stage 33: per-user remote identity, revocable grants and encrypted sync,
   isolated accounts, backup/restore before shared device use.
8. Stage 34: scheduled tasks and notifications with opt-in repeat intervals,
   timezone correctness, persistent cancellation and no silent provider calls.
9. Stage 35: bounded tool/computer use with a disposable sandbox, approval before
   every external action, recovery and budget limits.
10. Stage 36+: multiuser collaboration, high-fidelity artifact creation,
    plugin directory, multimodal video, code agent and independent safety audits.

This order is an engineering **roadmap**, not a promise of unattended future
implementation. The original independent real Railway-volume backup/restore
(#104) and live authenticated human pilot (#70) stay hard launch gates.

## Stage 27 behavior and boundaries

- Every NEXUS Work Mode project has a **default** profile: name NEXUS,
  style balanced, empty user instructions and no memory. Old encrypted
  archives missing these fields load in a backward-compatible way.
- A user can edit the project-local assistant name (1–64 characters), style
  (concise/balanced/detailed), optional instructions (maximum 400 characters)
  and **up to eight** explicit memory items of maximum 240 code points each.
  These are preferences and claims, not an AI system prompt or human judgment.
- Apply changes, then Save to include them in the existing AES-256-GCM
  encrypted project archive. Unapplied editor fields are not saved; no
  automatic memory inference, background web request, server sync or provider.
- Prepare a task context explicitly to see a bounded **1500-character draft**
  with at most the last three memory items. Private project files, notes,
  API tokens, other projects and unreviewed editor text are excluded. The
  preview labels user instructions as nonauthoritative preferences. It is not
  automatically sent, even to NEXUS. Sending from the online Work Mode is
  separately approved using the pre-existing consent and token controls.
- Editing assistant style or memory does **not** mark tasks complete or void
  human evidence. Editing goal/acceptance criteria still triggers the prior
  review invalidation rule. File export as plaintext does not include memory;
  separately exported encrypted archive does.
- The Android offline edition remains network-disabled, and the custom
  profile does not add network permission, microphone, inference, cost,
  shared credentials, live chat or automatic action.
- Source-controlled tests: legacy migration, type and size abuse, untrusted
  prompt fields, secret exclusion, audit/review authority, ciphertext privacy,
  correct passphrase recovery and cross-vault portable restore. Browser tests
  verify explicit editor+save, no automatic network calls and FA localization.
  Android emulator rechecks previous working local data behavior.

**Release truth:** completion in this PR does not equal production release,
full ChatGPT feature parity, or the existence of an LLM. Main/Render/Railway
remain unchanged; Stage27 runs only in the Work Mode development stack.
A_out <= A_in; human judgment remains final.
