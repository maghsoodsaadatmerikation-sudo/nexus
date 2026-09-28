# Main branch governance

The `NEXUS PR Verification / readonly-verification` job checks proposed changes with repository read permission. The same job runs the locked Rust and Artifact 05 tests, static authority checks, and the workflow authority boundary check. `NEXUS Cloud Adapter Verification / contract` remains a read-only path-specific PR check.

Exact candidate evidence and attestation run on `main` after merge. The v2.3, v2.4, and v2.5 evidence workflows have no pull request event and cannot execute proposed code with OIDC or attestation permissions. Release workflows retain their separate exact candidate gates and explicit release intent.

## Enforced repository rule

GitHub repository ruleset [20870033](https://github.com/maghsoodsaadatmerikation-sudo/nexus/rules/20870033) was activated on 2026-09-28. Its default-branch target currently resolves to `main`. It requires a pull request and the `readonly-verification` check from GitHub Actions before updating `main`, and prohibits deletion and non-fast-forward pushes. There are zero required approval reviews for this single-maintainer repository. The check is required but a PR need not be up to date with the latest base commit (`strict_required_status_checks_policy: false`).

No bypass actors are configured. The ruleset API reports `current_user_can_bypass: never`. An administrative or other exceptional update would not become verification evidence merely by reaching `main`; the exact candidate must still pass its own verification and release gates. Inspect the live GitHub ruleset before relying on this dated observation because settings can change independently of the repository.

The PR check was [successful on PR #25](https://github.com/maghsoodsaadatmerikation-sudo/nexus/actions/runs/36394073968), and the [post-merge main verification](https://github.com/maghsoodsaadatmerikation-sudo/nexus/actions/runs/36394275608) was successful. Neither result establishes Stage D durable-host evidence or a new Seal.

This governance rule grants no runtime, epistemic, or release authority. `A_out <= A_in` and evidence != authority remain in force. Historical release tags stay immutable.
