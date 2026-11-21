# Studio: reviewed research, code and data handoff into chat

## Explicit tool requests in AI chat mode

The optional AI model bridge remains **text-only** and cannot execute tools.
When a user explicitly types a tool action such as `Open the data analysis tool`,
`Analyze this CSV`, `Run JavaScript`, `Remind me to review the notes`,
`Open GitHub pull requests` or `باز کن تحلیل داده`, the focused chat composer
offers a separate, reviewed tool surface instead of implying that the model
will perform the action. The user can dismiss the offer and preserve the draft,
or continue to a normal model request with the existing consent review.

Generic questions such as `How do I use GitHub?` and writing prompts remain
normal conversational requests. Existing slash commands and explicit public
research requests are still supported. In local-guide mode, the broader
advisory suggestions are unchanged.

Routing is a bounded local heuristic, **not** an autonomous AI tool planner:
classification alone never reads an account, accesses a microphone, uploads
a file, grants a permission, runs code, sets a reminder, or sends a model prompt.
Connected provider actions are still governed by the connector's separate
catalog, operation-specific review, and authority checks. UI handoff does not
prove the linked service or capability is available.

Chromium acceptance covers English/Persian explicit requests, draft
preservation, the model-mode generic-question boundary, and absence of network
calls from suggestions alone.

NEXUS Studio now provides an explicit **Use in next chat** action at the
output location for three existing tools:

- A public Wikipedia/Crossref research card: the source excerpt, HTTPS
  source URL, provider metadata and attribution are moved to the next
  chat composer as **unverified source content**. This does not register the
  card as a persistent project source. The existing *Keep as project source*
  action remains separate.
- A completed local JavaScript sandbox run: the inert output string, not
  the executed code or its Worker privileges, becomes a one-turn item
  labeled *Local code result · untrusted*. The sandbox still never gains
  access to NEXUS project archives or the model transport.
- A completed local CSV/TSV/JSON data analysis: the already-visible
  descriptive summary is staged as a one-turn item with the dataset name.
  It is not a claim of causality or mathematical certainty.

These actions call a single guarded `NexusStudioUI.stageChatContext` method.
A user must have an unarchived active conversation; no automatic model
request, new chat message, data upload or archive save occurs. The item
is visible in the existing removable attachment tray with the source label.
A label is capped at 160 characters, content at 131,072 characters, and
only four such attachments plus an optional saved writing document can be
selected for one turn. Unsafe or oversized content is refused rather than
silently truncated in the handoff. The **model-context compiler** applies
its separate strict bounds, selects partial excerpts and explicitly labels
them as UNTRUSTED, NOT complete files or system instructions.

After selecting an item, the user still must type the next question,
choose **Prepare model request**, inspect the exact content and explicitly
approve the optional configured model provider. A configured provider
may receive those excerpt bytes only after that approval. The local
reflection guide is explicitly non-generative and refuses to claim it can
reason over attached bytes.

Only attachment **names**, not tool-output contents, are retained with a
sent user turn; the text is not written to the project archive. Staged
items are cleared on project, thread and branch changes, lock, or
successful model reply, with the same asynchronous cancellation boundary as
local file attachments. Previous model replies depending on this private
one-turn material cannot regenerate it from a filename.

This does **not** grant Studio a ChatGPT model, autonomous tool calls,
full-web retrieval, true scientific source verification, Python execution,
PDF/image understanding, image/video generation, real-time voice or
background automation. Those capabilities still require their own
implementation, execution service, authorization or provider integration.

Validation uses `scripts/test-studio-chat-tool-handoff-browser.py` in real
disposable Chromium with a synthetic model status and responder, a
synthetic Wikipedia record, actual local sandbox execution and real local
CSV analysis. It checks no automatic provider submission, non-persistent
source selection, visible reviewed content, untrusted provenance and
hand-off cancellation. The static installable Studio bundle and service
worker use the exact deterministic updated HTML digest.
