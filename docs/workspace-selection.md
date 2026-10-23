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

Run `node scripts/test-workspace-ui.mjs` with Node 20 or later. Eighteen tests execute
the actual inline application code with a synthetic DOM and deferred transport.
They cover mismatched selection, cleared/preserved drafts, create/import/export,
late loads, duplicate clicks, in-flight writes and selection changes during file
reading. Canonical read-only Verify invokes the suite; it neither accesses a
user's workspace nor uploads private backups. Request inspection is covered in
[the retained-status UI contract](request-status-inspector.md). This harness does not by itself
prove browser rendering or real server behavior.

## Executed browser witness

`python3 scripts/test-workspace-browser.py` requires an installed Chrome/Chromium
and Node 22 or later, and fails closed when either is absent. Canonical Verify runs it on the hosted Linux
runner. A local DevTools connection observes only the newly started private
browser process and waits for a completed report using real elapsed time,
including asynchronous File reads; virtual-time dumps are not used.
It adds synthetic transport and assertions only to a disposable copy of
the committed HTML, uses private temporary browser profiles, and leaves the
application source unchanged. No operator token, real workspace, external API,
production endpoint or user backup is involved.

The real browser exercises disabled controls, explicit judgment targeting,
late-load rejection, duplicate clicks, uncertain sent writes, File input import,
escaped evidence rendering, and read-only request-status semantics with late-response rejection. Ten completed checks are required at each of
two layout classes: a narrow stacked layout and a wide two-column layout. Actual
viewport width, browser version and bounded witness scope are logged in JSON.
The browser build comes from the hosted runner image and is recorded rather than
claimed to be pinned. Both Cargo.lock files and the Rust toolchain remain as-is.

The driver rejects missing reports, failed assertions, wrong layout classes and
process failures; browser exit code zero alone is not a PASS.

The private target endpoint may lag its port-file publication: connection and
observation timeouts are retried only within a bounded startup deadline. Page
actions, assertions and failed reports are never retried or waived.

This is real DOM and computed-layout evidence with synthetic in-page transport, not real-server
authentication, physical Android testing, a pixel-perfect visual review, or
production readiness. Passing it creates no authority and does not clear restore
quarantine or publish a Seal.

Browser driver failures emit one bounded JSON diagnostic to stderr naming the
stage (devtools-port, page-target, debugger-address, debugger-connect or
completed-report), elapsed milliseconds, and process/launch failure booleans.
It omits browser stderr, page content, URLs and profile paths. This diagnostic is
failure evidence only; it neither retries a witness nor changes acceptance,
startup deadlines, authority, or production verification.
