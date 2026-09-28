# Main branch governance

The `NEXUS PR Verification / readonly-verification` job checks proposed changes with repository read permission. The same job runs the locked Rust and Artifact 05 tests, static authority checks, and the workflow authority boundary check. `NEXUS Cloud Adapter Verification / contract` remains a read-only path-specific PR check.

Exact candidate evidence and attestation run on `main` after merge. The v2.3, v2.4, and v2.5 evidence workflows have no pull request event and cannot execute proposed code with OIDC or attestation permissions. Release workflows retain their separate exact candidate gates and explicit release intent.

The GitHub `main` ruleset must require pull requests and the stable `readonly-verification` check, reject force pushes and branch deletion, and document any administrator bypass. A direct administrative push or bypass is a governance exception; it is not verification evidence. The current ruleset state must be checked in GitHub, independently of this file.

This change grants no runtime, epistemic, or release authority. `A_out <= A_in` and evidence != authority remain in force. Historical release tags stay immutable.
