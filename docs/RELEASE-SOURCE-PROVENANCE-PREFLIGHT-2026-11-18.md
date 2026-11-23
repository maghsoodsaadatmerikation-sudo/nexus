# Release source identity preflight (18 November 2026)

## Threat / motivation

A successful `workflow_run` event and `head_branch: main` are *not sufficient*
to authorize a release. A completed run can originate from a fork's branch
also named `main`, from an unexpected workflow, a pull request, a manual
dispatch, a rerun, or a no-longer-current commit.

The existing historical `release-v1.6.yml` through `release-v2.5.yml`
workflows have separate release intent/evidence checks. The new preflight
**does not replace** them or silently authorize any publication.

## Delivered now

- `scripts/release-run-provenance.py`: deterministic, offline, fail-closed
  checker of independently fetched GitHub run, repository, and current-main
  metadata. No network or write capability in the validator.
- `scripts/test-release-run-provenance.py`: adversarial synthetic tests for
  forked sources, unexpected workflow, PR/dispatch runs, reruns, failed runs,
  stale SHA, malformed/duplicated JSON, and wrong repository identity.
- `.github/workflows/release-source-preflight.yml`: **manual opt-in only**,
  read-only GitHub metadata fetch. Requires an exact current main SHA and
  source run ID. It never publishes, deploys, signs, tags, or contacts providers.
- `pr-verify.yml`: new offline tests on every PR with read-only token.

## Invariants checked

1. The source run ID is an integer and belongs to this exact repository ID.
2. Both run repository and head repository identities match the live repository:
   a fork with its own `main` is rejected.
3. The verifying workflow's name and path match a pinned, version-specific
   catalogue; a similarly named replacement is not accepted.
4. The source event is a `push` to `main`, completed on the first attempt
   with conclusion `success`, not a PR, dispatch, schedule or rerun.
5. The source run head, trusted verifier checkout, and current live `main`
   are the **same exact 40-character SHA**.
6. Metadata parsing rejects duplicate JSON properties, invalid encoding,
   oversized files and non-finite numbers. Missing fields deny admission.
7. This check only accepts metadata as evidence *for a human to evaluate*;
   it does not itself elevate authority or prove service deployment.

## Use on GitHub Actions

Once merged to `main`, open **Actions > NEXUS Release Source Preflight —
Read Only > Run workflow**. Choose a release version and supply the exact
source run ID and current `main` SHA. No local computer is needed.

This manual workflow checks the current head only. Do not interpret a
historical run's successful release as a PASS against today's main.

## Known conservative hold

`v1.8` verification is itself triggered by `workflow_run` from
`NEXUS Verification`, instead of a direct `push`. The current preflight
**intentionally rejects** that chained origin. Supporting the nested
chain safely requires independently linking and validating the parent
push-run ID; merely allowing the string `workflow_run` is not enough.

## Not yet enforced in publishing workflows

**The existing publishing workflows have NOT been modified.** A metadata
preflight in an independent read-only workflow is diagnostic and cannot
block their `gh release create` steps. Before calling this a release security
remediation, an owner-reviewed change must require this gate:

1. From a trusted, pinned default-branch checkout **before** candidate checkout
   or executing candidate code, fetch live repository, original run, and
   current main metadata through read-only GitHub API calls.
2. Validate using this module. On any mismatch, abort.
3. Keep the existing exact-candidate intent, artifact hash and attestation
   checks; do not replace these with a metadata claim.
4. Revalidate immediately before `gh release create` to close the most obvious
   time-of-check/time-of-use window (still subject to races on remote mutation).
5. Inspect independent exact-head CI, sign off the trust boundary and merge
   only after the rollout plan passes security review. Do not apply elevated
   permissions to PR workflows. Keep `A_out <= A_in`.

The read-only check does not establish durable host, recovery/restore,
independent attestation, authenticity of third-party code or deployment
readiness. An untrusted contributor able to alter trusted main workflow
logic remains a separate governance/branch-protection threat.
