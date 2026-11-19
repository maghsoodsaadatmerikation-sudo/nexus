# NEXUS Zen Chat — 20 November 2026

This is a chat-first presentation and navigation upgrade, not a new generative model, API integration, private credential, or public deployment.

## What changed

- **Chat is the first screen on mobile and desktop.** The original four-tab mobile dock is visually replaced by a compact menu, home, new-conversation and capabilities header. All existing feature panels remain mounted; choosing **Advanced workspace** returns to the original full interface.
- The menu mirrors the current session's conversation history without copying it to new storage. Search, project controls, the private archive and memory settings remain accessible. The original archive encryption, export and retention behavior are unchanged.
- In **Local reflection guide** mode, explicit slash commands such as `/music`, `/orchestra`, `/research`, `/data`, `/chart`, `/code`, `/tasks`, `/write`, `/sources`, `/astrology`, `/sky` and `/memory`, plus a limited set of clearly recognizable Persian/English requests, show a proposed relevant tool. Unmatched prompts use the pre-existing local guide.
- A proposed tool is **never executed by the chat router**. The user must open it and review its normal controls. Only explicitly supplied slash arguments for research, local source search and orchestra prompting can be staged into the target field; the typed composer text remains unsaved and unchanged.
- In optional AI-model mode, exact-context review, separate consent, and the original model gateway remain mandatory. The local reflection guide is not generative AI.
- A compact black, purple and green layout follows the existing approved NEXUS logo. Advanced conversation actions appear through the `···` menu. Keyboard-accessible dismiss, dialogue focus cycling, and Persian RTL labels are included.

## Safety and deployment limitations

The UI introduces no network call, secret, telemetry, background execution, auto-save or external action. The existing conservative intent matching cannot reliably understand every natural-language instruction, and cannot substitute for a generative AI tool-calling backend. The static web bundle and digest-pinned service worker were updated alongside the source; the bounded public HTML asset cap was increased from 450 KB to 475 KB.

Verification requires the source-build checks and real-browser regression suite. GitHub commits do **not** mean the hosted Render website has been updated, because Studio AutoDeploy is disabled. Real Android accessibility and production deployment remain separate acceptance checks.
