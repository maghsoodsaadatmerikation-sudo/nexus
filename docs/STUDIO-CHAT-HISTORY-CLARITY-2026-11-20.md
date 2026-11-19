# NEXUS Studio — clear storage state & complete local chat history (2026-11-20)

## Problems fixed
- The compact conversation drawer previously mirrored the old hidden history pane. When the pane had its own search or archived filter, conversations disappeared from the drawer even though they remained in the session.
- Multiple conversations have the default “New conversation” name, making identification difficult.
- The initial chat had verbose storage copy but no compact saved/unsaved indication next to its title.

## Changes
1. The drawer searches **all active local-session project conversations**, irrespective of the legacy pane's search state. Type to find a project name, conversation title, or message text. Results show a short first-user-message preview for unnamed conversations and project context.
2. Archived conversations are hidden by default but visible after an explicit **Show archived** toggle. The list limits initial rendering to 80 matches and asks the user to narrow the search, avoiding an unbounded DOM.
3. A new read-only selection API and guarded open-conversation API reuse the existing draft-discard confirmations. Cancelled navigation leaves the drawer open and the unsent draft untouched.
4. A compact status under the NEXUS chat title distinguishes **Temporary · not saved**, **Unsaved changes**, and **Archive unlocked**. “Archive unlocked” does not claim a new encrypted save happened. The existing save and vault buttons are unchanged.
5. RTL/Persian labels, keyboard/focus handling and responsive touch sizes remain available; no message contents are ever sent to a search server.

## Acceptance
- Browser regressions exercise searching a message while the old history pane returns zero matches, switching to a different local thread, finding and opening archived conversations, restoring them, and confirming status transitions before and after encrypted save.
- Rebuild both standalone and public Studio from their source modules and re-pin the static PWA digest and byte count.
- Do not claim public Render deployment without a separate verified deployment and readback.
