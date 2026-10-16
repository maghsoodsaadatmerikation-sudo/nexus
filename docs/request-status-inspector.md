# Read-only retained request status

The web workspace includes **Check a request**, sharing the API token field.
Enter the exact ID returned at admission and explicitly check retained status.
No loaded workspace is required. Inspection sends only authenticated
`GET /v1/requests/{id}`, with `cache: no-store`. It never submits a POST, replays
or resumes work, creates an AuthorizedRequest, or changes workspace data.

IDs are opaque: spaces, slashes and Unicode are preserved and URL-encoded, never
trimmed or normalized. Empty IDs and IDs over the durable 100 UTF-8-byte limit
are rejected before transport. The response must echo the exact ID and contain
either `pending` or `indeterminate`. Malformed JSON, another ID, or invented
states such as `completed` leave the outcome unknown.

- `pending`: acceptance recorded; completion is not established.
- `indeterminate`: outcome unknown; do not blindly resubmit. Inspect independent evidence.
- HTTP 404: no retained record; this does not establish whether execution occurred.
- HTTP 401: check authentication. Other HTTP/network failures leave the outcome unknown.

Only one lookup runs at a time. Changing the request ID or token clears old
feedback and invalidates a late response; comparisons also reject programmatic
changes that did not dispatch an input event. A bounded ten-second read aborts
without retrying. The button is released on success or failure. This feature does not use local/session storage, change the address bar,
download these values or log them. The ID necessarily travels in the GET path
and may appear in server/proxy access logs; the token travels in the Authorization
header. Server error bodies are not echoed into the UI.

Twelve Node interaction tests execute the actual inline JavaScript, including
opaque IDs, byte bounds, all response meanings, malformed/mismatched responses,
network errors, stale ID/token responses, duplicate clicks and injected abort.
The real Chrome witness also clicks the panel in narrow and wide layouts,
checks the meanings of pending/indeterminate/404/401, and rejects stale feedback
while asserting only GETs were sent. Its backend is synthetic in-page transport;
existing HTTP contract tests verify the actual authenticated gateway status API.
This does not certify physical Android behavior or production availability.

A retained marker is evidence, not authority or a durable executor-outcome
journal. A_out <= A_in, the AuthorizedRequest boundary, CT-001..020 and separate
Bootstrap/Verify stages remain required. Both Cargo.lock files remain pinned.
Status inspection grants no capability, clears no quarantine and establishes no
new Seal or production readiness.
