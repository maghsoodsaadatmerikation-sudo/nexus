# NEXUS Studio — capability comparison and operating contract

Reviewed 13 November 2026 against the current repository, the separately retrieved
Stage 27 Android prototype, and official OpenAI documentation:

- https://learn.chatgpt.com/docs/features
- https://learn.chatgpt.com/docs/projects
- https://learn.chatgpt.com/docs/customization/memories
- https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create

This is a functional comparison, not a claim to reproduce ChatGPT's models,
service scale, security guarantees, quality, or every account-specific feature.
Studio is a new integrated page at `/studio`; it does not replace the existing
judgment workspace or migrate the separate Android prototype's local archives.

## What this implementation adds

| Capability | Before | This implementation |
| --- | --- | --- |
| Project conversation library | Guided session only; separate prototypes | 12 projects, 60 named threads per project, 400 graph nodes per thread |
| Search, rename, archive, delete | No integrated conversation library | Local full-text search includes preserved branches; archived threads are opt-in |
| Edit an earlier message | No conversation branches | A new branch preserves the original nodes and answer |
| Alternative model answers | No model reply path | Review a new request from the same user node; original answers remain selectable |
| Temporary conversations | Tab-only guided chat | Default remains tab-only; no automatic plaintext persistence |
| Persistent history | No integrated saved graph | Explicit encrypted browser save and reopen, encrypted portable backup and import |
| Controlled memory | Prototype project preferences | User-authored/editable/removable project memory; excluded from prompts unless selected |
| Custom assistant instructions | Separate prototype | Project preferences included as untrusted user context, below the fixed server policy |
| File-grounded context | File desk and manual excerpts | UTF-8 TXT/Markdown/CSV/TSV/JSON lexical retrieval; exact passages and source/line labels visible before sending |
| Writing canvas | Downloadable files, no versioned editor | 20 documents per project, 30 immutable saved versions, comparison and explicit restoration into a draft |
| Conversation/document export | Separate tools | Plaintext Markdown export requires confirmation; encrypted session export remains separate |
| Long conversation handling | Session cap | The model receives a bounded recent path, with omitted earlier-message count shown; no fabricated summary |
| Generative text model | Deterministic guide, no model | Optional authenticated server bridge; requires an operator-configured real provider |
| Stop and late-response isolation | No model transport | Abort waiting and reject stale responses after edits, project changes or lock |
| English/Persian accessibility | Existing bilingual offline tools | English-first Studio, Persian/RTL and a complete local interface language-pack importer/template; inert text rendering |
| Read aloud | Existing browser adapters | Explicit read-aloud using an available local device voice only |
| Live source retrieval | Provider search destinations only | Explicit direct Wikipedia excerpts and Crossref metadata, with source/provenance cards |
| Local code execution | Inert text only | Explicit JavaScript execution in an opaque-origin Worker, with network/storage isolation, timeout and output bounds |
| Data charts | Separate local analysis tools | Validated bar/line JSON to local Canvas and explicit PNG export |
| Optional personal transits | No integrated astrology profile | Explicit On-line Astrology data retrieval, local tropical contacts, encrypted project profile and opt-in guide/model context |

The model bridge is **implemented but not provisioned with a real model** by this
change. A synthetic HTTP provider verifies the transport contract, not reasoning
quality, truthfulness, model availability, provider billing, or model quality.
The local reflection guide remains visibly non-generative. No automatic fallback
pretends a reflection prompt is an AI answer.

## Chat-first temporary file context (November 2026 follow-up)

The conversation composer now supports explicitly selected **one-turn text file
excerpts** (TXT/Markdown/CSV/TSV/JSON), plus the latest saved writing
document. Bounded local retrieval and the exact passages are visible in the
existing reviewed model request. Source files are not stored in the project
archive; only filenames are associated with human chat turns, with an
explicit "not saved" warning. The local scripted guide cannot read them.
The model is still optional and requires a properly configured real provider.
See [the operational and security contract](STUDIO-CHAT-ATTACHMENTS.md).

This is *not* multimodal model vision, PDF/OCR parsing, unrestricted file
uploads, source verification or a substitute for real ChatGPT model quality.

## Calendar reminders

In focused chat, enter `/remind Review the next mix` and open **Reminders**.
Choose the date, local clock time, one-time/daily/weekly recurrence, and the
alert lead time. **Download calendar file** exports an iCalendar event and
display alarm. Import the file into your calendar and check its time zone and
alert settings. The receiving calendar interprets the local clock time and
handles recurrence and alerts. Studio builds the file locally and clears the
reminder form when switching projects or locking the workspace.

## PDF text attachments

In the public or phone-local Studio, open **Attach text files to this message**
and choose **Attach a PDF**. The browser extracts selectable text with its
packaged PDF.js 6.5.438 worker. It reads up to the first 20 pages of a file up
to 2 MiB and labels passages with page numbers. Studio attaches temporary text
rather than storing the PDF. When using a model, the existing request preview
shows the excerpts before sending.

Image-only scans require OCR before import. Password-protected PDFs and complex
reading order are not supported reliably. Offline extraction is available after
**Prepare offline use** caches the parser and worker. The original PDF is
never sent to a server by this import. See [PDF.js](https://mozilla.github.io/pdf.js/).

## Direct chat handoff from the existing local tools

Studio now exposes **Use in next chat** actions on explicitly fetched public
research cards, finished local JavaScript Worker results and completed local
data-analysis summaries. The actions stage clearly marked, bounded
**untrusted one-turn excerpts** in the existing chat attachment tray,
with no automatic model requests or persistent source registration.
Source content is still included only after human review and explicit
model-send approval. See [the operating contract](STUDIO-CHAT-TOOL-HANDOFF.md).

This is user-directed data flow; **not autonomous model tool calling,
open-ended research, tool-execution authority, or a trained model**.

## Study mode and interface language

English is the initial interface and installable app language. Persian is
available through the language selector, with right-to-left layout when chosen.

Select **Study mode** below the message field to work through a question in
steps. The local study guide offers a self-explanation and practice prompt.
For a configured model, the request preview displays the tutoring instruction
before the learner approves the send. Changing the option invalidates a
pending review. The option resets when switching conversations or clearing
private state.

## Chat dictation

Open **Dictate** from the conversation composer. Studio shows a disclosure before
asking the browser to start speech recognition. The browser may send microphone
audio to its speech service. Support depends on the browser, device permissions
and recognition locale. Studio uses Persian (Iran) with the Persian interface and
the selected interface locale elsewhere.

Finish dictation to append recognized text to the existing draft. The transcript
stays in the composer for editing and follows the existing send and save controls.
Editing the draft, switching conversations, hiding the tab, or clearing private
state cancels an active recording and discards its pending text. Studio's existing
read-aloud action uses device voices. See [browser speech recognition support](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition).

## Core feature comparison, 20 November 2026

The comparison covers the workflow users can reach from Studio. OpenAI describes
its capabilities in the [capability overview](https://help.openai.com/en/articles/9260256-chatgpt-capabilities-overview),
[release notes](https://help.openai.com/en/articles/6825453-chatgpt-release-notes),
[Projects guide](https://help.openai.com/en/articles/10169521-projects-in-chatgpt)
and [sharing guide](https://help.openai.com/en/articles/7925741-sharing-conversations-and-scheduled-tasks-in-chatgpt).
Availability in ChatGPT varies by account, client and plan.

| Workflow | NEXUS Studio implementation | Open work |
| --- | --- | --- |
| Compose and use answers | Copy an answer, prepare an alternate answer in the focused chat, and stage a paste that would overflow the draft as temporary reviewed text. The paste can be up to 128 KiB. Compatible gateways can show streamed answer text after request approval. Finished replies format Markdown headings, lists, quotes, tables, code and HTTPS links. | Rich-text paste and further formatting such as math. |
| History, projects and sharing | Local search, branches, archives and transcript export. Project-level instructions and manually curated memory. | Share links, multi-user access, cross-device sync and opt-in retrieval across project chats. |
| Files, data and writing | One-turn excerpts from supported text files and selectable PDFs, separate spreadsheet analysis and charts, and a versioned writing canvas. | Scanned PDF OCR, richer Office and audio ingestion, a reusable binary file library and model-assisted editing. |
| Models and tools | Optional authenticated gateway with opt-in streaming, local reflection guide and optional limited device model. Tool recommendations require user review. | Hosted model provisioning and reliable model-driven use of approved tools. |

Short pastes still go into the draft. Studio preserves the draft when staging a
long paste and requires a separate question and the existing request review.
Regeneration is disabled while a draft or temporary attachment is open. It
continues to create an alternate branch after model approval.

An operator can enable streamed answers on a [compatible model gateway](../nexus-cloud/README.md#optional-studio-model-bridge).
While the answer is arriving, Studio shows it as a preview. Successful completion
adds the full answer to the current branch. Stop and interrupted delivery discard
the preview and preserve the user draft.

## Remaining service prerequisites

The [ChatGPT Plus and Pro comparison](https://chatgpt.com/pricing/) is the
reference for the consumer-plan features below.

| ChatGPT capability | NEXUS boundary after this change | Required next dependency |
| --- | --- | --- |
| Hosted frontier-model reasoning | No hosted model/key supplied | A funded/authorized provider or a separately hosted local model with sufficient compute |
| Live web retrieval / deep research | Review and run up to four queries, one per line, against Wikipedia, Crossref or both. Duplicate results retain their matching queries, and selected sources can be exported or attached to the chat. | Broader search APIs, source verification, model/tool orchestration and source-quality evaluations |
| Image understanding / OCR | The chat image picker and bounded PNG/JPEG vision route are implemented with separate consent and an operator-set request allowance | Compatible vision provider, deployment verification and quality tests, including OCR |
| Image/video generation | Not implemented | A connected generation provider, usage authorization and media QA |
| Real-time voice conversation | Opt-in microphone dictation and local read-aloud | A real-time audio provider, microphone permissions, interruption tests and device QA |
| Sandboxed Python/code execution | JavaScript Worker lab available; no Python or OS execution | An isolated Python/OS execution service with resource/network limits and reproducibility checks |
| Scheduled unattended work and push notifications | Calendar export for reminders. In-app background jobs and push delivery are pending | A durable job runner, delivery channel and user-specific authorization |
| Third-party app actions/MCP | Configured gateways can expose reviewed GitHub and Render operations. A general-purpose app catalog is pending | Per-service OAuth, scoped tokens, concrete tools, revocation and action review |
| Shared projects and live collaboration | Single browser owner only | User accounts, tenancy, encrypted sync, access control and conflict resolution |
| Cross-device automatic history sync | Portable encrypted file only | An authenticated sync service and account recovery design |
| All-language reviewed localization | English/Persian bundled; other interface languages accept complete local packs | Reviewed bundled translation packs and accessibility testing for additional languages |
| Native Android release | Existing Stage 27 test APK is separate | Maintained native source, stable signing identity, real emulator/device acceptance and publishing |

## Privacy and persistence

All projects, graph nodes, memories, source text and document versions remain in
the current browser tab until explicitly saved or exported. Saving uses a
separate IndexedDB database (`nexus-studio-v1`), AES-256-GCM with fresh IVs and
PBKDF2-SHA-256 (310,000 iterations). Passphrases require at least 12 Unicode
characters. Archive revision compare-and-swap rejects cross-tab stale writes.
Encryption provides confidentiality of stored bytes; it is not account security,
protection from a compromised device, or independent audit attestation.

The total clean state is capped at 4 MiB. Source files are UTF-8 text, at most
256 KiB each and 12 per project. Text is never rendered as HTML or executed.
Removing memory stops its future inclusion but does not erase earlier transcript
text. No automatic memory inference occurs. Other threads/projects are never
automatically inserted into a prompt. Global local-history search is a separate,
explicit user action. The UI rejects unsaved profile/canvas drafts before archive
save, so applied and unapplied work are not silently conflated.

Archives contain project source text, not the original file binaries. PDF attachments are temporary text extracts. Office layout parsing, semantic embedding search and OCR are outside this implementation. Existing
file-desk and analysis tools are separate. Retrieval is lexical, case-insensitive,
Unicode-aware search over bounded source passages. A name/line label identifies
supplied text; it does not independently verify that text or validate a model's
assertions about it.

## Optional model gateway

The Rust production service serves Studio and a truthful unconfigured model
status. The optional Python cloud adapter provides the text-only model gateway.
It can be run from the repository root with the existing locked Python project:

```bash
uv run --project nexus-cloud uvicorn main:app --app-dir nexus-cloud --host 127.0.0.1 --port 8000
```

An operator must set these server environment variables through their secret
configuration system; never place the provider key in the page, Git or a public
artifact:

| Variable | Meaning |
| --- | --- |
| `NEXUS_MODEL_URL` | Exact Chat Completions-compatible endpoint; HTTPS, or literal loopback HTTP for a separately running local model |
| `NEXUS_MODEL_ID` | Exact model ID supported by that provider |
| `NEXUS_MODEL_API_KEY` | Optional provider credential, held on the server; unnecessary for a provider that legitimately requires no key |
| `NEXUS_STUDIO_TOKEN` | Separate gateway access credential of at least 32 characters, entered transiently in Studio; never forwarded to the model |
| `NEXUS_STUDIO_ORIGIN` | Optional exact allowed Studio origin when UI and gateway are hosted on different origins |

The cloud deployment must include the repository's `web/studio.html` to serve
its own `/studio` page. A deployment restricted to `nexus-cloud` can still serve
the gateway API, with an explicitly configured cross-origin Studio connection.
A ChatGPT subscription is not silently converted into provider credentials.

A user first checks the model configuration. The page then prepares the exact
message path, preferences, selected memory and selected source passages. No
content is sent until the user approves that prepared request. Approval includes
a configuration fingerprint; a changed model/endpoint requires a new review.
Credentials stay outside project state, ciphertext and exported transcripts.
The gateway adds the NEXUS policy as a system message, disables provider storage
where the compatible API supports that parameter, uses no tools, follows no
redirects and rejects tool-call responses. The fixed policy is a prompt and not
proof of a model's alignment. Provider retention terms still apply.

Requests are capped at 96,000 bytes and 42 messages; text replies at 24,000
characters and provider JSON at 128,000 bytes. A 45-second total deadline and
four-request capacity bound apply. Context preparation retains at most 40 recent
messages and reports omissions. Stop discards a late response, but cannot promise
that a remote provider stops computing or reverses charges. No retry is automatic.

## Validation

- 40 synthetic state/encryption checks, including immutable branch preservation,
  malformed imports, memory isolation, bounded long context, wrong passwords,
  authenticated ciphertext, revision conflict, lock cancellation and erase.
- 58 Python transport/model tests, including real loopback HTTP with a synthetic
  compatible provider. No real model or provider key was used.
- Narrow and wide real Chromium acceptance covers history, branches, source text,
  inert rendering, approved model-context transport with a fixture, regeneration,
  late-response discard, real IndexedDB ciphertext, draft protection and reopen.
- Synthetic empty-layout screenshots are produced in CI for visual review.
- Existing Rust core/gateway checks remain required. A separate HTTP contract
  verifies `/studio`, no-store responses and the unconfigured model status.

Physical Android, actual provider output quality, unattended background execution,
notifications, live collaboration and a new signed APK are not verified here.

## Research and code/data lab follow-up

See [the operating contract and verification](RESEARCH-CODE-LAB.md) for direct
public source retrieval, isolated local JavaScript execution and chart rendering.
Source text remains unverified; code execution is explicit, local and separate
from the writing canvas. These tools do not provision a language model or a
Python/OS environment.

See [Optional astrology](OPTIONAL-ASTROLOGY.md) for its exact provider, privacy, calculation and interpretation boundaries.

The [offline ephemeris and general style](OFFLINE-SKY-TONE.md) now support local natal/transit computation and an inspectable, switchable general presentation heuristic without runtime website requests.

The [integrated quality upgrade](QUALITY-UPGRADE-2026-11-13.md) shares bounded numerical analysis across the offline app and Studio, adds source ranking, recoverable removals, direct chart/canvas flow and capability/navigation controls.
