# Workspace selection and human intent

The browser binds edit and download actions to the workspace actually loaded in
memory. Editing the workspace ID field selects a possible target; it does not
load that target or authorize writing to it. Claims, alternatives, human judgment
and download controls remain disabled until selected and loaded IDs match.
The action functions also check the match before transport, so a programmatic
field change cannot bypass the UI guard.

Loading, creating or importing a different workspace clears claim/source,
alternative/consequence and decision/rationale drafts before enabling edits.
Refreshing the same workspace preserves its drafts. No draft is automatically
submitted. The question and displayed records always come from the adopted
snapshot, and the connection indicator names the loaded workspace.

Only one workspace operation runs at a time in a tab, including reading an import
file. An ID input event invalidates the active operation's view generation. Before
transport and after its response, that generation must still match. A late
response cannot reset the selected ID or replace displayed records after an ID
change. A selection change while reading an import file blocks the write before
sending. A write already sent may have taken effect: the UI does not cancel,
rollback, replay or blindly retry it. Load the intended workspace to inspect
server state. Changing away and back still invalidates an in-flight response.

This protects against accidental cross-workspace actions within one browser tab.
It is not multi-tab/server concurrency control, draft persistence, optimistic
locking, transport authentication, a cryptographic identity proof, or a core
permission grant. ID equality does not construct AuthorizedRequest. A_out <= A_in,
evidence != authority, CT-001..020 and Bootstrap/Verify separation remain intact;
both Cargo.lock files remain pinned. A browser success message is not Seal or
production readiness and request acceptance is not proof of execution completion.

Run `node scripts/test-workspace-ui.mjs` with Node 20 or later. Seven tests execute
the actual inline application code with a synthetic DOM and deferred transport.
They cover mismatched selection, cleared/preserved drafts, create/import/export,
late loads, duplicate clicks, in-flight writes and selection changes during file
reading. Canonical read-only Verify invokes the suite; it neither accesses a
user's workspace nor uploads private backups. This harness does not by itself
prove browser rendering or real server behavior.
