# Workspace authentication context

Changing the API token through the input handler invalidates in-flight workspace and request-status observations, clears the loaded snapshot, question, drafts and rendered evidence/judgment/history, and requires an explicit authenticated reload. The workspace selector remains available as a locator, never as authorization. Nothing is saved in browser storage.

Workspace operations bind both their selection generation and exact token at entry. A token change during file reading or transport prevents subsequent admission or snapshot adoption/export. Already sent writes may have taken effect: there is no cancellation, automatic retry, rollback or claim of nonexecution. A token change and change-back through input events still invalidates old operations. Programmatic token differences without input events are rejected at API and loaded-snapshot guards; arbitrary script control of the page is outside this UI safety boundary.

Eighteen Node interaction tests include late load/write/export, changed tokens with and without input events, change-back, clearing rendered content, and reloading under the new token. Real Chrome dispatches actual input and verifies clearing, late-response rejection and explicit reload at two widths (ten checks per layout) with synthetic transport. Neither harness establishes physical Android or production availability.

This prevents accidental mixing of browser contexts; the server still authenticates and authorizes every request. It creates no AuthorizedRequest, increases no authority (A_out <= A_in), and evidence remains non-authoritative. CT-001..020, pinned Cargo.lock files and Bootstrap/Verify separation remain required. No production promotion or new Seal is implied.
