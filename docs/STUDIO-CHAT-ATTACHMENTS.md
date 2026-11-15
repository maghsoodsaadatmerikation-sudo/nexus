# Studio — chat-first one-turn file and writing context

## What changed

NEXUS Studio already offers project conversations, encrypted project archives,
source search, a versioned writing canvas and an optional generative model
gateway. Previously, the user had to leave the chat composer and manually
register source text in the project Sources panel before a text excerpt could
be included in a model request.

The **Conversation** composer now contains **Attach text files to this
message**. Users can add up to four **TXT, Markdown, CSV, TSV or JSON** files,
up to **128 KiB each**, and can optionally include the **latest saved version
of the selected writing document**. The document is an additional,
explicitly checked temporary context item. No file bytes are sent by
selection alone.

The new context compiler reads text locally as strict UTF-8, performs a
bounded lexical search over selected attachments, and provides a clearly
labeled partial excerpt per selected file. If there is no matching keyword,
it includes a bounded excerpt from the start of each selected file rather
than silently ignoring an attachment. Each excerpt records a filename,
line number, character offset and whether the file was partially included.
Only five items and approximately 8 KiB of excerpt text can enter a model
prompt, subject to the existing total context cap.

The exact source passages are included in the existing **Prepare model
request → Exact context to send → Explicit approval** flow. They are
clearly marked **UNTRUSTED, not complete file content**, not system
instructions and not verified facts. The user can inspect the text before
approving the provider request. A real generative answer still requires an
operator-configured provider or separately installed compatible local model.

## Privacy, lifecycle and honesty

- Attachments are **not automatically enrolled as project sources**, not
  uploaded when selected, and not written to the encrypted project archive.
  The actual source text stays only in the current page memory before
  explicitly approved use. Only original filenames or a saved document's
  title/version label are recorded on the human turn as provenance.
- The conversation view and explicit Markdown transcript export show the
  attachment labels with a warning that bytes were **not saved**. Their
  presence does not prove a model used or correctly cited a passage.
- Selection is cleared after a successful model reply, project or thread
  switch, branch switch, editor selection change, lock or archive reopen.
  Late asynchronous browser file reads are rejected after replacement and
  cannot silently appear in a newly opened project.
- The local scripted reflection guide does **not** claim it can read
  attached files. It explicitly declines a guided turn until temporary
  files are cleared or a real model request is prepared.
- A model reply generated with one-turn files cannot be regenerated using
  the old filename alone. Studio instructs the user to edit into a new
  branch and reattach the files.
- Selected document context uses only the most recent **already saved**
  version, never the unsaved canvas draft. The corresponding provenance
  marker is only a label. If a project is saved, the document's saved
  version is already part of that explicit encrypted project archive.
- Existing project memory and automatic project source lexical retrieval
  remain separate, independently controlled opt-in checkboxes. Arbitrary
  attached file text cannot become system policy, a human judgment or a
  registered project claim.

## What this does NOT implement

It does not parse PDF or Office attachments in the chat composer, perform
image or video understanding, OCR, voice transcription, embeddings, a
vector database, provider tool calls, live web search, document authenticity
verification, unrestricted file upload, cross-session storage of binary
attachments, or autonomous model research. Existing separate NEXUS file-desk
features can preserve and inspect more file types, subject to their own
review/consent limits.

The optional model gateway is still text-only and does not claim ChatGPT
model quality, training, account memory, image generation, real-time voice
conversation or third-party application integration.

## Verification

- `scripts/test-studio-chat-attachments.mjs` checks bounded attachment
  metadata, persistence of **filenames only**, explicit untrusted excerpts,
  partial-file disclosures, opt-in project source isolation, malformed
  records and model-role abuse rejection.
- `scripts/test-studio-chat-attachments-browser.py` uses real Chromium to
  exercise direct file selection, no network on attachment selection,
  local guide denial, reviewed and consented model transport to a **synthetic
  provider**, saved-document excerpt inclusion, filename provenance in
  conversation, no file bytes in encrypted project state, PDF refusal,
  regeneration refusal and late-file completion isolation after lock.
- The deterministic `web/studio.html` bundle and offline
  `public/studio/index.html` plus hashed service worker are regenerated
  to carry the same functionality. Studio and Static Studio CI must pass
  their exact bundle checks and real browser acceptance.

Synthetic model replies prove the *transport and UX contract*, not
generative model reasoning or production deployment. No NEXUS runtime
authority or imported machine-history permission changes.
