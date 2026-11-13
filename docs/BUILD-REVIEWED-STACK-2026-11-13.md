# NEXUS tested integration branch (development-only)

The read-only rehearsal in PR #158 identified the exact source conflicts
and tested the six-PR stack with a Rust 1.85-compatible lockfile, explicit
preservation of newer gateway feature routes and older Studio endpoints.

This new action separates test authority from GitHub write authority. The
first job has `contents:read`, merges and tests the code in an ephemeral
GitHub Actions runner, then produces a patch+manifest. The second job has
`contents:write` but executes no candidate source, checks the immutable
patch SHA and current main SHA, rejects existing targets, and creates **only**
`integration/nexus-reviewed-stack-20261113`. No force, provider operation,
main update, deployment, recovery key or release Seal is possible by design.

A green build is necessary but not sufficient: ambiguous conflicts were
resolved provisionally with main favored, and security/feature semantics
require independent review. The original Railway volume still lacks an
independently verified full offhost restore; Render main auto-deploy remains
enabled. The integration branch must stay Draft/unmerged until then.
