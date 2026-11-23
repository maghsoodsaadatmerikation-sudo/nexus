# Temporary workflow outcome receipts — 24 November 2026

NEXUS Studio's `/plan` feature is **not an autonomous agent**. Users author two to six slash-command steps, explicitly open each tool, review the tool's own permissions and operation, and manually acknowledge each step before continuing. Nothing starts from parsing or opening a plan.

## Additional scope

When an approved local **Code** or **Research** action actually begins after the relevant step has been opened, its UI controller emits an in-tab lifecycle event. The reviewed workflow listens only for the matching currently open step and matching local run identifier. It shows:

- Started: the local controller began the requested operation, but no result has been accepted.
- Succeeded: the controller reported local code completion or successful source retrieval. This does not establish reasoning correctness, evidence quality, source truth or independent execution proof.
- Partial: some research sources failed or the research hit its deadline.
- Failed: the local controller rejected or could not complete its operation.
- Cancelled: the user or cleanup invalidated an in-flight action, with no completed result claim.

Opening a tool does **not** create an execution receipt. A result from an earlier run, a different tool or an old workflow cannot complete the current step. Human acknowledgment is a **separate field**, not another form of runtime evidence. Research results are source leads only. Other tools currently have no local lifecycle receipt and remain explicitly self-reported.

## Optional export

**Download review report** is a user-initiated unencrypted JSON export. The user is warned that it includes their workflow command text. The export contains only command identifiers, the typed command text, opened flag, user acknowledgment, in-tab observed outcome, and `authority: none`; it excludes tool output bytes, model messages, credentials, archive contents, project identifiers, third-party data and timestamps. Nothing is stored automatically.

The document has no signatures, remote receipts or independently verified success claims. Changing the draft, project or conversation, or clearing private data invalidates the ephemeral report. No background scheduling, autonomous model tool call, provider authorization or external mutation is added.

## Review and regression

```sh
python3 scripts/build-studio.py --check
python3 scripts/build-studio-static.py --check
python3 scripts/test-studio-chat-tool-handoff-browser.py
python3 scripts/test-studio-browser.py
node --check web/studio-composer-ui.js
node --check web/studio-lab-ui.js
```

Real-browser acceptance checks an actual isolated local JavaScript worker, visible outcome without automatic advancement, explicit human acknowledgment, unencrypted report consent, schema and scope, cancellation, and invalidation on draft changes. A browser test is not a real-world host witness or proof of model quality.
