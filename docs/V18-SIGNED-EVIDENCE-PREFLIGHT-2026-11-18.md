# NEXUS v1.8 — signed evidence subject preflight (2026-11-18)

## Security purpose

The v1.8 flow is `NEXUS Verification` (main push) ->
`NEXUS v1.8 Independent Rebuild` (workflow_run) ->
historical privileged release workflow. Parent/rebuild IDs and matching SHA
are not sufficient proof of authentic evidence.

This phase adds a **separate, opt-in, read-only** verification workflow that
uses GitHub CLI's attestation verifier and a narrow second validation of the
verified certificate repository ID and exact subject SHA-256.

## Added code

- `scripts/release-v18-attestation-subject.py` performs only **offline**
  validation of JSON output from a *previously successful* `gh attestation
  verify --format json`. It independently hashes the local evidence bytes and
  checks the signed SLSA subject SHA-256, certificate repository ID from
  `verificationResult.signature.certificate.sourceRepositoryIdentifier`, and
  the signed predicate type.
- `scripts/test-release-v18-attestation-subject.py` exercises malformed
  results, untrusted predicates, renamed/reused repository IDs, duplicate JSON
  keys, fake/missing hashes, binary mutation, ambiguous subjects and oversize
  input. The tests use simulated results only; they do **not** generate a
  trustworthy signature.
- `.github/workflows/release-v18-signed-preflight.yml` is manual
  `workflow_dispatch` on main, with `contents/actions/attestations: read`
  and **no write permission**. It fetches the two exact GitHub run records,
  the repository and main branch metadata, and the evidence artifact.
  Then it uses `gh attestation verify` to enforce:
    - exact repository and signer workflow path;
    - `refs/heads/main` source ref and exact source digest;
    - GitHub-hosted runners, not self-hosted.
  On successful cryptographic verification only, it runs the offline subject
  check and the prior two-hop consistency check.
- `pr-verify.yml` runs only adversarial synthetic tests, without credentials
  or a live artifact download.

## Required manual inputs after owner-reviewed merge to main

1. Exact 40-character lowercase SHA of the **current** main head.
2. `NEXUS Verification` parent push run ID.
3. `NEXUS v1.8 Independent Rebuild` child workflow_run run ID.

Runs fail closed when input is stale or metadata disagrees. The preflight is
intentionally unavailable on unreviewed branches. GitHub CLI version and
trusted roots should be pinned/reviewed before any broader deployment.

## Boundaries

- The JSON checker **does not verify signatures**; only a successful,
  identity-constrained `gh attestation verify` invocation does.
- Evidence's `statement.predicate` is signed but contains data provided by
  the originating workflow. It cannot establish truthful external execution
  by itself.
- The attestation confirms the signer workflow and evidence artifact digest,
  not the complete truth of parent/child causal ancestry or the physical
  independence of builders.
- Existing release workflows still **do not consume** this gate. This phase
  adds diagnosis, not mandatory release authorization or deployment.
- The latest main branch can move between metadata checks and other operations.
  Production release workflows would require a fresh guard at publication
  time, as well as branch protections and operator review.
- Public Studio workflow startup failure remains a separate issue; a failed
  zero-job Actions run is not evidence that user-facing browser tests failed.

`A_out <= A_in`: no new publication, secrets, model tool authority, release,
tag creation or hosting mutation.
