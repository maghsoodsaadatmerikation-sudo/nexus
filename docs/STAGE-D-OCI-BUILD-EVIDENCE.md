# Stage D — pinned Python OCI runtime and unsigned build evidence (synthetic only)

## Actual change, not a production deployment

This stage extends the existing synthetic-only guarded container built and tested in PR #239. The original Rust gateway baseline revision remains \`f4d027bb5f7e715b298f7cf7184fa621a2fb071d\`. The *builder* is still \`rust@sha256:0ff31c9ffa641a62e48d543fb00b4960955ea375f40776f40f585b89e654cc5e\`. The new *runtime* is **\`python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c\`**. That OCI index digest was independently resolved in an exact GitHub Actions run against Docker Hub on 15 November 2026.

The previous runtime used \`apt-get update\` and an unversioned \`python3-minimal\` package, so the installed Python and its transitive OS dependencies were not fixed. The new image **does not invoke apt or pip at build time** and uses the verified official Python runtime from the immutable OCI index digest, with its Python binary at \`/usr/local/bin/python3\`. The real Rust gateway executable is still compiled from its exact historical Git commit using \`cargo build --locked\`, with the pinned \`Cargo.lock\`.

**Important:** pinning OCI bases, Python, and Cargo.lock makes major inputs *identifiable*, but is **not yet a reproducible image build**. Compiler nondeterminism, GitHub runner/compiler implementation, apt-derived contents already inside the upstream base, provenance of base images, and attestation of fetched Rust crates remain independent trust questions.

## Local evidence produced by CI

New file: \`scripts/stage-d-oci-image-evidence.py\`.

The CI runs \`capture\` after actual \`docker build\` and the existing synthetic HTTP/restart test. It gathers:

- GitHub exact PR head SHA and the explicitly selected historical gateway Git commit;
- exact builder and runtime OCI index digest references;
- SHA-256 of the reviewed Dockerfile, the historical \`Cargo.lock\`, and every reviewed guard script copied into the historical build context;
- the **local Docker image ID and image configuration** (non-root UID 10001, exact default guard ENTRYPOINT, no implicit CMD or VOLUME, synthetic-only labels);
- actual Python version reported by the container;
- installed Debian package names and versions reported read-only by \`dpkg-query\` inside an isolated networkless image;
- Rust package names, versions and available lockfile checksums from the historical \`Cargo.lock\`;
- a **partial CycloneDX 1.5 software inventory** derived from those inputs.

The output comprises a canonical \`manifest.json\`, a canonical \`sbom.cdx.json\` and a file containing their exact SHA-256 digests. The separate \`verify\` mode requires the manifest's **exact trusted expected SHA-256**, checks the schema, guarded image identity, all syntactically valid hashes, the SBOM linkage and all explicit release-denial fields. With \`--image\`, it also checks that the locally loaded image ID matches the captured ID. It never treats these reports as proof of a published image digest or as signing-key authorization. The \`release-gate\` mode intentionally **always exits nonzero**, even if the manifest and SBOM agree.

The job uploads the manifest, partial SBOM and local checksums as a **7-day GitHub Actions artifact** with a full-SHA pinned \`actions/upload-artifact@v7.0.1\` action. This is reviewable CI output, **not a supply-chain signature**, a separately custodied hash, a signed provenance attestation, or a registry-pinned image. The CI's verification uses a digest calculated in the **same runner**; it is an internal consistency check only. To establish external custody, an independent reviewer must fetch the artifact from the specific GitHub Actions run and retain and compare its digest outside the build runner.

No \`docker push\` command is used. The image and data are discarded with the ephemeral runner. No actual Railway or Render service is woken, redeployed, reconfigured or backed up.

## Why this step remains synthetic

The image's default OCI ENTRYPOINT still delegates to the guarded-start verifier; the container accepts only private synthetic \`/data\` and a separate read-only operator policy, a pinned modern binary SHA, and loopback-only binding. The guard **hard-denies** known-unsafe old recovery SHA \`588dc7672146031425b16b34956876d644244ace\`. Existing historical Stage D volumes and their sleeping service versions remain unchanged.

The local Docker image ID cannot be substituted for a registry's immutable \`name@sha256:...\` digest. A Docker daemon administrator can override ENTRYPOINT or change mounts unless independently enforced admission controls prevent that action. **No deployment-level deny-override policy is provisioned here.**

The partial CycloneDX inventory is deliberately not called a complete SBOM: it enumerates \`dpkg\` packages and Cargo.lock declarations, but does not prove complete dynamic library/runtime dependencies or the authorship of any upstream component. Signed, externally retained provenance, policy-bound registry digest, a verified runner environment, a separate real recovery host, approved fresh disposable volume and controlled destructive restore still need review.

## Running the evidence checks

The dedicated GitHub Action \`NEXUS Stage D Guarded OCI Image — Synthetic Only\` runs the image test, captures build evidence, verifies its own snapshot, proves the release-gate returns nonzero, and uploads a short-retention artifact. The new offline regression script \`scripts/test-stage-d-oci-image-evidence.py\` tests malicious manifest field changes, forged signature/registry/release assertions, tampered package inventories, unsafe aliases, invalid SHA-256 pins and malformed JSON. That offline test is also included in the mandatory \`readonly-verification.sh\` gate.

**No approval:** always \`release_authorized=false\` and \`release_gate=BLOCKED\`. Production promotion requires independent image attestation and a separate operator-approved deployment policy, not just a green synthetic CI.
