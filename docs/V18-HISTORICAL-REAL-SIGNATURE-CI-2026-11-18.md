# Historical v1.8 signed-evidence integration acceptance — 18 November 2026

## Why this exists

Previous release-chain and attestation-subject tests use **synthetic** JSON fixtures.
They do not demonstrate that the GitHub CLI can verify an actual artifact
attestation. This additional workflow performs a true, bounded, **read-only**
cryptographic verification of the existing public v1.8 artifact in PR CI.

## Historical source (fixed, never treated as today's release candidate)

- Repository: `maghsoodsaadatmerikation-sudo/nexus`
- Rebuild run: `44222980195`; artifact `v1.8-independent-rebuild-evidence`
- Source SHA: `1ee30f7784420f27bba5d5d5798d9cdf3b64c89f`
- Original JSON size: 933 bytes
- Original JSON SHA-256:
  `220b08c8c41f875679cbb18044746dc00f7e3d16e8d5a411cd276a0fd02a4474`
- Expected signer workflow:
  `.github/workflows/v1.8-independent-rebuild.yml`

## Enforcement

`.github/workflows/v18-historical-signed-evidence.yml`:

1. Uses a GitHub-hosted runner with **contents/actions/attestations read only**.
   No deploy credentials, releases, tags, secrets, OIDC write or token persistence.
2. Downloads only the fixed original historical artifact from its exact run ID.
3. Checks file size, SHA-256 and byte-for-byte equality with the committed
   known reference fixture.
4. Invokes GitHub CLI's **cryptographic** `gh attestation verify` against live
   repository attestations, constraining signer workflow, main source ref,
   exact historical source SHA and non-self-hosted-runner provenance.
5. Only on successful verification, feeds its JSON output to the independent
   subject-digest/repository-ID checker. Any missing or unmatched element fails.
6. Reports `HISTORICAL SIGNED EVIDENCE: VERIFIED READ-ONLY`, never
   `RELEASE_AUTHORIZED` or `PRODUCTION_READY`.

The exact-head PR CI result—not this document—is the decisive evidence that
real end-to-end historical signature verification succeeded. If the attestation
is unavailable, stale, or wrong, the workflow *must fail closed*.

## Explicit limitations

- Historical signature validation is not permission to publish *current main*.
- The attacker-controlled payload of a signed workflow still requires
  architectural trust and independent release intent checks.
- No changes were made to privileged historical publishing workflows.
- The separate Public Studio zero-job failure is unresolved; absence of jobs
  does not diagnose browser functionality or the precise startup cause.
- Stacked draft PRs must be reviewed in dependency order, not merged blindly.

Authority invariant: `A_out <= A_in`.
