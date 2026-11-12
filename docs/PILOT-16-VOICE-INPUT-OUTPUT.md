# Pilot 16 — opt-in microphone and read-aloud

Use the Voice panel to select a workspace field, speech language and voice.
Read-aloud can read the selected field (including an unsubmitted draft) or a
committed report. Passwords are excluded by a fixed target allowlist. Reading
is explicit, bounded to 5000 characters and cancellable between short chunks.
No voice or microphone starts automatically. Available languages and voices
come from the browser/device; interface language does not assert speech support.

## Microphone → preview → draft → explicit registration

Start microphone begins one session, limited to 60 seconds. Final recognition
results enter a private editable preview. Interim/duplicate/late results cannot
write workspace data. Insert as draft uses the captured field/caret only if
both workspace and target text are unchanged; length overflow and changed text
are rejected without truncation or overwriting. A human judgment is never
registered by speech input. The user must still use the normal Register action.
Preview text is included in the unregistered-input warning but excluded from
JSON, reports and encrypted checkpoints until inserted and explicitly committed.

Stop audio aborts recognition, cancels the read queue and invalidates late
callbacks. Page hide/unload, a hidden tab, interface/voice setting changes and
workspace replacement stop audio. Workspace replacement clears the old preview
only after the existing replacement confirmation. Setting changes retain the
preview so it can be reviewed or copied. Reading does not consume a dictation
preview. NEXUS creates no audio recording file or persistent audio/transcript
store and does not create a speech-server account.

## Local default and explicit online choice

The default uses voices marked local by the browser and requires recognition's
processLocally=true support. It never silently falls back to online recognition.
If the browser lacks local support or a model, the UI explains the limitation
and suggests the device keyboard microphone as another input method. A separate
Download local speech model action requires confirmation and may use network
and browser storage; it does not start the microphone.

Allow browser online speech services is off by default. If selected, each
recognition session separately confirms possible audio transmission to the
browser provider. Each nonlocal/unknown voice read separately confirms possible
selected-text transmission. Native browser services may use internet outside
the page's connect-src policy; CSP is not a promise of offline/private processing
for these opted-in native services. Language translation still makes no network
calls. NEXUS itself adds no API token, provider subscription or paid server.

## Verification and limits

The voice witness runs 35 DOM/adapter checks per viewport in real disposable
Chromium with controlled SpeechRecognition/SpeechSynthesis adapters. It verifies
no auto start, local-only enforcement, consent cancellation, final-only preview,
length/conflict rejection, explicit registration boundary, stop/error/deadline
cleanup, no password access, late-event rejection, model-install separation,
language/page/workspace cancellation and no new app network/storage.
These are **not actual hardware audio, microphone capture, native permission
prompt, provider accuracy or audible speaker tests**. A headless CI environment
has no owner's microphone/speaker. Real speech availability and recognition
accuracy depend on their browser, selected language and installed models/voices.

The English/Persian catalogs include all voice labels; a new complete language
template is required for older custom packs. Builder checks embedded catalogs,
message-count metadata and exact worker source hash. Public source identity,
public-origin adapter behavior and offline reopening are separate checks.
Original Railway recovery and authenticated human-server use remain separate.

Official browser references:
- https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API/Using_the_Web_Speech_API
- https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition/processLocally
- https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesisVoice/localService
