# NEXUS Studio — one-step conversation onboarding (2026-11-20)

## User problem

The Zen Chat home made chat the first screen, but an empty session still required creating a named project, choosing a new conversation and returning to the composer before the user could ask anything. Typed text did not enable the quick action without a thread. The capability chips could overwrite an unsent draft.

## Implemented

- The first typed message enables the existing quick composer even without a project. On its first explicit action, the UI creates **one temporary local project and conversation**, preserving the user's exact typed text, before delegating to the existing local guide or reviewed model-request flow.
- A **Start chatting** onboarding button performs that local setup in one action. The header's **New conversation** action also works when no project exists and otherwise uses the existing draft-discard protection.
- The initial local project is named **My conversations** or **گفتگوهای من**, depending on selected UI language. Users can still create named projects in the existing Projects panel.
- Capability hints such as `/music` are still suggestions, not automatic execution. The Music/Research/Files quick chips no longer overwrite non-empty private drafts: when text exists they only navigate to the tool while retaining the draft.
- The chat input now has a natural English/Persian placeholder, with its semantic label preserved for screen readers. All previously implemented features and full-workspace access remain available.

## Safety contract

- Nothing is automatically saved, sent to a model, transferred to the hosting provider or committed to an encrypted archive. Local project creation occurs only after a real user action.
- Existing model exact-context review, separate send consent, vault encryption and unsaved-work warnings remain authoritative. An archived conversation cannot be replied to until the user starts a fresh one.
- The small intent matcher is not model-based and cannot reliably interpret arbitrary instructions; proposals still require the user to open and operate the tool.
- The new local setup refuses to replace unapplied forms or temporary tool work while creating a first project. The user's draft is retained across the first setup. A subsequent New Chat still uses the existing confirmation for unsent drafts.
- No new provider credentials, browser storage keys or network APIs.

## Verification

The deterministic Studio and static PWA bundles were rebuilt and the source-bound worker digest updated. Browser regression coverage now includes one-click first chat, preservation of typed draft, disabled empty-message actions, consent-first tool navigation, non-destructive capability chips, and encrypted/offline workflows. Run the required PR checks before merge.

**Deployment**: merging source does not prove the live Render site was updated, because Studio AutoDeploy was disabled in the reviewed deployment configuration. Android hardware validation and public-origin asset readback are separate from CI.
