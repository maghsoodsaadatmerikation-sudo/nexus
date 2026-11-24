# Private workflow checkpoint store (internal candidate)

A standard-library SQLite store records review acknowledgments and cancellation across process restarts. It binds a workflow ID to the reviewed plan digest and requires the original plan at each read or mutation. It stores identifiers, digest, revision, acknowledgments, cancellation and operation records, not the plan prose. These records may still be sensitive.

A transaction serializes revision checking and event insertion. A repeated identical operation ID returns the current view and original applied revision without adding an event; a conflicting reuse or stale revision is rejected. Dependency readiness is checked before acknowledgment. Cancellation and all-acknowledged states are terminal. There is no external tool execution, and execution_authorized remains false.

This is an internal operator-local library, not a network endpoint. The operator must create a private directory and secure DB/rollback journal permissions, provide trusted validated plans, enforce ownership, quota and retention, and arrange backups. SQLite must be on a supported local filesystem. No encrypted storage, account isolation, crash/power-loss acceptance, external side-effect exactly-once guarantees, or deployment are claimed. No new external service is needed. A later API must add user authentication and storage lifecycle before exposing the library.

Regression tests cover reopen, same-operation replay, changed plan, invalid dependency, stale revision, cancellation, concurrent writers and separate IDs. Full cloud adapter CI remains required.
