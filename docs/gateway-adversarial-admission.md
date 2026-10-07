# Gateway adversarial admission lab

The HTTP contract suite challenges 32 synchronized tasks on cloned routers using four Tokio workers. It requires exactly one delegation for a repeated ID (31 conflicts), four admissions for a rate budget of four (28 throttles), and three admissions for capacity three (29 unavailable responses). Every assertion checks delegation counts as well as HTTP status.

A panic-on-poll body demonstrates that unauthorized POST requests are rejected before body polling. A separate fresh-state counterexample deliberately accepts the same ID twice across independent AppState instances: replay protection is process-local, not durable or distributed. Passing this test documents a limitation; it does not certify restart safety or exactly-once execution.

Run: `cargo test --locked --manifest-path artifact-05/Cargo.toml --test http_contract adversarial_ -- --nocapture`. Five named tests must execute and pass; a zero-test result is not evidence.

These tests add evidence, not authority. They grant no capabilities and do not replace the AuthorizedRequest boundary or CT-001..020. A_out <= A_in remains the core invariant. Existing Bootstrap and Verify stages remain separate and both Cargo.lock files remain pinned. No Seal, production readiness, durable replay, or external deployment is claimed.
