# NEXUS v1.8 two-hop source and evidence audit — 18 November 2026

## Structural issue

The v1.8 release chain has two distinct GitHub Actions steps:

1. **NEXUS Verification**: direct `push` on `main`.
2. **NEXUS v1.8 Independent Rebuild**: a `workflow_run` triggered after verification.

A second, privileged release workflow observes the rebuild. Its event's
`success` and `head_branch=main` values alone are insufficient to
demonstrate a trustworthy origin. The first release-source preflight
intentionally denied all `workflow_run` sources, including v1.8.

## Implemented (read-only)

- `scripts/release-chain-v18-audit.py` checks BOTH independently supplied
  run metadata objects against the exact current main SHA and repository ID.
- The parent must be a successful first-attempt **push** to main from the
  pinned `NEXUS Verification` workflow path.
- The rebuild must be a successful first-attempt **workflow_run** from
  `.github/workflows/v1.8-independent-rebuild.yml` in the same repository
  and pinned to the same SHA.
- The published reproducibility evidence JSON must name **both exact run
  IDs**, the SHA and two byte-identical 64-hex executable hashes, while
  preserving its non-authorizing claims.
- Unknown evidence fields, malformed IDs, forks, reruns, missing builders,
  mismatched hashes, stale main, and false claims fail closed.
- `scripts/test-release-chain-v18-audit.py` supplies synthetic adversarial
  fixtures with no GitHub network calls or production credentials.
- `pr-verify.yml` runs those tests before resource-intensive verification.

## Trust limitation

`CONSISTENT_ONLY` **does not mean cryptographic ancestry or release
authorization**. A JSON file supplied as input can be forged. Before
applying any result to a publishing workflow, an independent reviewer must
verify the downloaded artifact's *subject digest and signer workflow identity*
using a patched and pinned GitHub CLI, and examine whether the parent-to-child
relationship is sufficiently authenticated. The validator does not infer
that two runs with matching SHA were causally linked.

As of this implementation, the existing release workflows and the opt-in
`release-source-preflight.yml` have **not** been modified by this phase.
The owner-only publication decision and all release intent/evidence gates
remain separate. No deployment, tag, release or production mutation.

## Release-readiness acceptance

- Local synthetic tests: PASS is necessary but not sufficient.
- Exact-head GitHub Actions PR CI: must be green.
- Independent artifact attestations: require separate verification.
- Owner-reviewed provenance integration: still pending.
- Main merge and public deployment: still pending.

All changes preserve `A_out <= A_in`.
