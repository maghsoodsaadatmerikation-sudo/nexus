# NEXUS v1.8.0 — Independent Rebuild Reproducibility

Status: **SEALED / VERIFIED AT THE STATED REPRODUCIBILITY BOUNDARY**

Constitutional invariant: `A_out <= A_in`

## Exact release identity

- Tag: `v1.8.0`
- Candidate commit: `8acb5c8045e4ed62123f36ccf31f2058ad4a164a`
- NEXUS Verification run: `34970085439` — SUCCESS
- Independent rebuild run: `34970263941` — SUCCESS
- GitHub Release: published, non-draft, non-prerelease

## Independent rebuild evidence

Two separate GitHub-hosted `ubuntu-24.04` jobs checked out the same exact candidate and independently built the repository Dockerfile with its digest-pinned Rust base. Each extracted `/usr/local/bin/nexus` from its independently built image.

- Builder A executable SHA-256: `53dda74dee2a7665d2425247ca430cced7aa696d6822e22d2fbeb63fc5b69c0e`
- Builder B executable SHA-256: `53dda74dee2a7665d2425247ca430cced7aa696d6822e22d2fbeb63fc5b69c0e`
- Result: **EXACT MATCH**
- Reconciled evidence SHA-256: `39bcd8494685a45aaa8443df314e3522b80be4bd5400722b6337868014727fb5`

The reconciliation job itself completed successfully and attested/uploaded the evidence before the release gate evaluated the candidate.

## Operational boundary

- Production mutation performed: NO
- Railway service/volume/deployment created for v1.8: NO
- Paid upgrade required: NO
- Secret value recorded in v1.8 evidence: NO
- Authority expansion: NONE

## Claim discipline

This release establishes byte-identical gateway executable output for the exact v1.8 candidate across the two independent GitHub-hosted rebuild jobs in the recorded run under the stated pinned build definition.

It does not claim reproducibility across arbitrary platforms, architectures, toolchains, future runner images, providers, or build systems. It does not establish source correctness, provider correctness, universal security, universal availability, or formal epistemic correctness.

Historical v1.0.0 through v1.7.0 boundaries remain historical evidence and are not rewritten by this release.
